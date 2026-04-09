"""NexusGuard — Roles & Permissions API"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.models.models import Role, Permission, UserRole, User, RiskTier, AuditCategory
from app.services.sod_engine import SoDEngine
from app.services.audit_service import AuditService
from datetime import datetime, timezone

router = APIRouter()


class RoleAssignInput(BaseModel):
    user_id: UUID
    role_id: UUID
    business_justification: str
    expires_at: Optional[datetime] = None


@router.get("/")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "display_name": r.display_name,
            "system_name": r.system_name,
            "risk_level": r.risk_level.value,
            "is_sensitive": r.is_sensitive,
            "is_privileged": r.is_privileged,
        }
        for r in roles
    ]


@router.post("/assign")
async def assign_role(
    data: RoleAssignInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Assign a role to a user — runs SoD check first."""
    user = await db.get(User, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = await db.get(Role, data.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # ── SoD Pre-check ──
    sod = SoDEngine(db)
    sod_result = await sod.check_role_assignment(data.user_id, data.role_id)

    if not sod_result["can_proceed"]:
        return {
            "assigned": False,
            "blocked": True,
            "reason": "SoD violation detected — assignment blocked",
            "violations": sod_result["blocking_violations"],
        }

    actor_id = UUID(current_user.user_id) if current_user.user_id else None
    user_role = UserRole(
        user_id=data.user_id,
        role_id=data.role_id,
        assigned_by=actor_id,
        business_justification=data.business_justification,
        expires_at=data.expires_at,
        status="active",
    )
    db.add(user_role)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.access_change,
        event_type="role_assigned",
        action="assign_role",
        outcome="success",
        actor_id=actor_id,
        actor_email=current_user.email,
        target_user_id=data.user_id,
        target_email=user.email,
        resource_type="role",
        resource_id=str(data.role_id),
        payload={
            "role_name": role.name,
            "justification": data.business_justification,
            "sod_warnings": sod_result.get("violations", []),
        },
        new_state={"role": role.name, "status": "active"},
    )

    await db.commit()
    return {
        "assigned": True,
        "user_role_id": str(user_role.id),
        "sod_warnings": sod_result.get("violations", []),
    }


@router.get("/permissions")
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(select(Permission))
    perms = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "resource": p.resource,
            "action": p.action,
            "system_name": p.system_name,
            "is_sensitive": p.is_sensitive,
        }
        for p in perms
    ]
