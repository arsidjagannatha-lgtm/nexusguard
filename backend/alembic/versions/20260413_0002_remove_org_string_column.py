"""remove_org_string_column — make organization_id the single source of truth.

PROBLEM BEING FIXED
-------------------
users.organization (VARCHAR 255) and users.organization_id (FK → organizations)
both existed, creating two sources of truth for the same fact. Any code that
wrote to one but not the other silently diverged. The String column was a
legacy artefact from before organizations was a proper table.

MIGRATION STEPS (in order)
---------------------------
1. SYNC   — Overwrite the String column with the real org name from the FK
             for every row where organization_id IS NOT NULL.
             This guarantees the String column is accurate before we
             use it as a fallback in step 2.

2. RESOLVE NULLS — For users where organization_id IS NULL, attempt to find
             a matching organizations row by exact (case-insensitive) name.
             This handles users inserted via the old API that passed only the
             String and no FK.

3. BLOCK   — Raise if any rows still have organization_id IS NULL after
             step 2. A NOT NULL constraint below would fail anyway, but
             raising here gives a human-readable error before hitting the DB.

4. NOT NULL — ALTER COLUMN organization_id SET NOT NULL. From this point the
             DB enforces referential integrity.

5. DROP    — DROP COLUMN organization. The String column is gone. All code
             must access org name via the relationship (user.org.name).

DOWNGRADE STEPS
---------------
1. Re-add the column as nullable (we cannot guarantee the old String values).
2. Back-fill it from organizations.name via the FK.
3. Set NOT NULL (safe now since every row has a valid org via FK).
4. Drop the NOT NULL constraint from organization_id (reverting step 4).

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    """
    Check whether a column exists in a table using information_schema.
    Works on PostgreSQL; safe to call at any migration state.
    """
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1
            FROM   information_schema.columns
            WHERE  table_schema = 'public'
              AND  table_name   = :tbl
              AND  column_name  = :col
        )
    """), {"tbl": table, "col": column})
    return result.scalar()


def _column_is_nullable(conn, table: str, column: str) -> bool:
    """Return True if the column currently allows NULLs."""
    result = conn.execute(sa.text("""
        SELECT is_nullable
        FROM   information_schema.columns
        WHERE  table_schema = 'public'
          AND  table_name   = :tbl
          AND  column_name  = :col
    """), {"tbl": table, "col": column})
    row = result.fetchone()
    return row is not None and row[0] == "YES"


def upgrade() -> None:
    conn = op.get_bind()

    org_col_exists = _column_exists(conn, "users", "organization")

    if org_col_exists:
        # ── Step 1: SYNC ──────────────────────────────────────────────────
        # Overwrite the String column with the canonical org name from the FK
        # for every row where organization_id IS NOT NULL.
        # This makes the name-based fallback in Step 2 reliable, and ensures
        # a clean downgrade() is possible if ever needed.
        synced = conn.execute(sa.text("""
            UPDATE users
            SET    organization = organizations.name
            FROM   organizations
            WHERE  users.organization_id = organizations.id
              AND  users.organization_id IS NOT NULL
        """))
        print(f"  ✔  Synced {synced.rowcount} users: String column ← org.name")

        # ── Step 2: RESOLVE NULLS ──────────────────────────────────────────
        # Users inserted via the old API (organization string only, no FK).
        # Attempt to find a matching organizations row by case-insensitive name.
        resolved = conn.execute(sa.text("""
            UPDATE users
            SET    organization_id = organizations.id
            FROM   organizations
            WHERE  users.organization_id IS NULL
              AND  LOWER(TRIM(users.organization)) = LOWER(TRIM(organizations.name))
        """))
        if resolved.rowcount:
            print(f"  ✔  Resolved {resolved.rowcount} null org_ids via name match")

    else:
        # The organization String column is already gone.
        # This happens when:
        #   (a) the migration was already applied and is being re-run erroneously, OR
        #   (b) the column was dropped manually outside Alembic.
        # Either way, Steps 1–2 are not needed. We still need to enforce NOT NULL
        # on organization_id and verify there are no orphan rows.
        print("  ℹ  users.organization column not found — skipping sync step "
              "(column was already removed)")

    # ── Step 3: BLOCK if unresolvable NULLs remain ────────────────────────
    # Build the query based on whether the String column is available for
    # the error message (it may already be gone).
    if org_col_exists:
        orphan_query = sa.text("""
            SELECT id, email, organization
            FROM   users
            WHERE  organization_id IS NULL
            LIMIT  20
        """)
    else:
        orphan_query = sa.text("""
            SELECT id, email, NULL AS organization
            FROM   users
            WHERE  organization_id IS NULL
            LIMIT  20
        """)

    orphans = conn.execute(orphan_query).fetchall()
    if orphans:
        detail = "\n".join(
            f"  • {str(row.id)[:8]}  email={row.email!r}"
            + (f"  org_string={row.organization!r}" if row.organization else "")
            for row in orphans
        )
        raise RuntimeError(
            f"\n\n"
            f"  MIGRATION BLOCKED: {len(orphans)} user(s) have organization_id = NULL\n"
            f"  and cannot be automatically resolved.\n\n"
            f"{detail}\n\n"
            f"  Fix options:\n"
            f"  1. Insert the missing organization into the organizations table,\n"
            f"     manually set users.organization_id, then re-run:\n"
            f"       alembic upgrade 0002\n"
            f"  2. Delete the orphan users if they are test/invalid rows.\n"
        )

    # ── Step 4: NOT NULL on organization_id ───────────────────────────────
    # Only alter if the column is currently nullable — ALTER COLUMN on a
    # column that is already NOT NULL is a no-op in PostgreSQL but can
    # produce confusing output; skip it explicitly.
    if _column_is_nullable(conn, "users", "organization_id"):
        op.alter_column(
            "users",
            "organization_id",
            nullable=False,
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        )
        print("  ✔  organization_id set NOT NULL")
    else:
        print("  ℹ  organization_id is already NOT NULL — skipping ALTER")

    # ── Step 5: DROP organization String column ───────────────────────────
    # Guard: only drop if it still exists (idempotent).
    if org_col_exists:
        op.drop_column("users", "organization")
        print("  ✔  users.organization (String) dropped — single source of truth achieved")
    else:
        print("  ℹ  users.organization already absent — nothing to drop")


def downgrade() -> None:
    """
    Re-add the String column and back-fill from the FK.
    Idempotent: safe to call even if the column was never dropped.
    """
    conn = op.get_bind()

    # Re-add only if absent (idempotent)
    if not _column_exists(conn, "users", "organization"):
        op.add_column(
            "users",
            sa.Column("organization", sa.String(255), nullable=True),
        )
        # Back-fill from the FK
        conn.execute(sa.text("""
            UPDATE users
            SET    organization = organizations.name
            FROM   organizations
            WHERE  users.organization_id = organizations.id
        """))
        # Make NOT NULL now that all rows are filled
        op.alter_column("users", "organization", nullable=False,
                        existing_type=sa.String(255))
        print("  ✔  users.organization (String) column restored and back-filled")
    else:
        print("  ℹ  users.organization already exists — skipping add_column")

    # Restore organization_id to nullable (matches original 0001 schema)
    if not _column_is_nullable(conn, "users", "organization_id"):
        op.alter_column(
            "users",
            "organization_id",
            nullable=True,
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        )
        print("  ✔  organization_id restored to nullable")
    else:
        print("  ℹ  organization_id is already nullable — skipping ALTER")

    print("  ✔  Downgrade complete")
