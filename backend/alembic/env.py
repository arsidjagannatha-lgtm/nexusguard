"""
alembic/env.py — NexusGuard async Alembic environment.

Key design decisions:
  - DATABASE_URL comes from app.core.config (reads .env), so credentials
    are never stored in alembic.ini or this file.
  - Uses async_engine_from_config so asyncpg is the ONLY driver needed —
    no psycopg2 install required.
  - Offline mode generates raw SQL for review/CI; online mode runs live.
  - compare_type=True so Alembic detects column type changes (e.g. Enum
    values added), not just new/removed columns.
  - include_schemas=False — all objects live in the default 'public' schema.
"""

import asyncio
import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Make app importable from the backend/ directory ──────────────────────────
# alembic is run from backend/, so 'app' is already on the path via
# prepend_sys_path = . in alembic.ini — but we add an explicit guard here.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import app config and all ORM models ──────────────────────────────────────
# Importing settings gives us DATABASE_URL from .env at runtime.
# Importing models ensures all Table objects are registered on Base.metadata
# so autogenerate can diff them against the live database.
from app.core.config import settings
from app.core.database import Base

# Import every model module so their classes register on Base.metadata.
# Add new model files here as the project grows.
import app.models.models  # noqa: F401 — side-effect import

# ── Alembic config object ──────────────────────────────────────────────────────
config = context.config

# Inject DATABASE_URL from settings so it's never hardcoded in alembic.ini.
# asyncpg URL (postgresql+asyncpg://...) works for both online and offline modes.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# ── Logging ───────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata for autogenerate ─────────────────────────────────────────
target_metadata = Base.metadata


# ── Helper: shared migration context options ──────────────────────────────────
def _migration_context_kwargs() -> dict:
    """Options passed to context.configure() in both online and offline mode."""
    return dict(
        target_metadata=target_metadata,
        # Detect column TYPE changes (VARCHAR → TEXT, Enum value additions, etc.)
        compare_type=True,
        # Do NOT compare server defaults (noisy and usually harmless)
        compare_server_default=False,
        # Render AS ENUM for PostgreSQL ENUM columns in generated migrations
        render_as_batch=False,
        # Include all tables NexusGuard uses
        include_schemas=False,
    )


# ── OFFLINE MODE ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Useful for generating SQL scripts to review or apply manually.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_migration_context_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


# ── ONLINE MODE ───────────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """Called synchronously inside the async connection context."""
    context.configure(connection=connection, **_migration_context_kwargs())
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine, open a connection, and run migrations.

    NullPool is used deliberately: Alembic runs as a short-lived CLI process
    and does not need connection pooling. NullPool also avoids 'connection
    already closed' errors when the event loop exits.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for live database migrations."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
