"""
NexusGuard — Segregation of Duties (SoD) Engine
Detects and manages SoD conflicts for external identities
"""
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.models import (
    SoDRule, SoDViolation, SoDStatus, SoDSeverity,
    UserRole, RolePermission, Permission, User
)


class SoDEngine:
    """
    Cross-system SoD conflict detection engine.
    Evaluates all role assignments against defined SoD rules.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_role_assignment(
        self,
        user_id: UUID,
        new_role_id: UUID,
        actor_id: Optional[UUID] = None,
    ) -> dict:
        """
        Check if assigning new_role_id to user_id creates SoD violations.
        Call BEFORE persisting the role assignment.
        Returns: {has_violations, violations, can_proceed, blocking_violations}
        """
        # Get permissions from the new role
        new_permissions = await self._get_role_permissions(new_role_id)
        if not new_permissions:
            return {"has_violations": False, "violations": [], "can_proceed": True}

        # Get all permissions the user currently holds
        existing_permissions = await self._get_user_permissions(user_id)

        # Get active SoD rules
        result = await self.db.execute(
            select(SoDRule).where(SoDRule.is_active == True)
        )
        rules = result.scalars().all()

        violations = []
        for rule in rules:
            perm_a = str(rule.permission_a_id)
            perm_b = str(rule.permission_b_id)

            new_perm_ids = {str(p.id) for p in new_permissions}
            existing_perm_ids = {str(p.id) for p in existing_permissions}

            # Check if new role + existing roles create a conflict
            conflict = (
                (perm_a in new_perm_ids and perm_b in existing_perm_ids) or
                (perm_b in new_perm_ids and perm_a in existing_perm_ids) or
                (perm_a in new_perm_ids and perm_b in new_perm_ids)
            )

            if conflict:
                violations.append({
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "severity": rule.severity.value,
                    "compliance_control": rule.compliance_control,
                    "description": rule.description,
                    "permission_a_id": str(rule.permission_a_id),
                    "permission_b_id": str(rule.permission_b_id),
                })

        blocking = [v for v in violations if v["severity"] in ("critical", "high")]
        return {
            "has_violations": len(violations) > 0,
            "violations": violations,
            "can_proceed": len(blocking) == 0,
            "blocking_violations": blocking,
        }

    async def scan_user_violations(self, user_id: UUID) -> List[dict]:
        """
        Full SoD scan for a user — evaluate all their current permissions
        against all active SoD rules. Creates violation records in DB.
        """
        existing_permissions = await self._get_user_permissions(user_id)
        if not existing_permissions:
            return []

        result = await self.db.execute(
            select(SoDRule).where(SoDRule.is_active == True)
        )
        rules = result.scalars().all()

        perm_map = {str(p.id): p for p in existing_permissions}
        perm_ids = set(perm_map.keys())
        found_violations = []

        for rule in rules:
            perm_a = str(rule.permission_a_id)
            perm_b = str(rule.permission_b_id)

            if perm_a in perm_ids and perm_b in perm_ids:
                # Check if violation already recorded and open
                existing = await self.db.execute(
                    select(SoDViolation).where(
                        and_(
                            SoDViolation.user_id == user_id,
                            SoDViolation.sod_rule_id == rule.id,
                            SoDViolation.status == SoDStatus.open,
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # Already tracked

                violation = SoDViolation(
                    user_id=user_id,
                    sod_rule_id=rule.id,
                    permission_a_id=rule.permission_a_id,
                    permission_b_id=rule.permission_b_id,
                    severity=rule.severity,
                    status=SoDStatus.open,
                    detected_at=datetime.now(timezone.utc),
                )
                self.db.add(violation)
                found_violations.append({
                    "rule": rule.name,
                    "severity": rule.severity.value,
                    "compliance_control": rule.compliance_control,
                })

        await self.db.flush()
        return found_violations

    async def get_violations_summary(self) -> dict:
        """Dashboard summary of all open SoD violations."""
        result = await self.db.execute(
            select(SoDViolation).where(SoDViolation.status == SoDStatus.open)
        )
        violations = result.scalars().all()

        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for v in violations:
            by_severity[v.severity.value] += 1

        return {
            "total_open": len(violations),
            "by_severity": by_severity,
            "critical_count": by_severity["critical"],
            "requires_immediate_action": by_severity["critical"] + by_severity["high"],
        }

    async def remediate_violation(
        self,
        violation_id: UUID,
        action: str,  # "revoke_permission_a" | "revoke_permission_b" | "accept" | "mitigate"
        actor_id: UUID,
        reason: str,
        mitigating_control: Optional[str] = None,
    ) -> dict:
        """Process remediation for a SoD violation."""
        violation = await self.db.get(SoDViolation, violation_id)
        if not violation:
            return {"success": False, "error": "Violation not found"}

        if action == "accept":
            violation.status = SoDStatus.accepted
            violation.accepted_by = actor_id
            violation.accepted_at = datetime.now(timezone.utc)
            violation.acceptance_reason = reason
            violation.mitigating_control = mitigating_control
        elif action in ("revoke_permission_a", "revoke_permission_b", "remediate"):
            violation.status = SoDStatus.remediated
            violation.remediated_by = actor_id
            violation.remediated_at = datetime.now(timezone.utc)
            violation.remediation_action = reason
        elif action == "mitigate":
            violation.status = SoDStatus.mitigated
            violation.mitigating_control = mitigating_control
            violation.remediation_action = reason

        await self.db.flush()
        return {"success": True, "new_status": violation.status.value}

    async def _get_role_permissions(self, role_id: UUID) -> List[Permission]:
        result = await self.db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        return result.scalars().all()

    async def _get_user_permissions(self, user_id: UUID) -> List[Permission]:
        result = await self.db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
            .where(UserRole.status == "active")
        )
        return result.scalars().all()
