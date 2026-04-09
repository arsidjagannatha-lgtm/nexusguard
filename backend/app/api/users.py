"""NexusGuard — Users API"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.models.models import User, IdentityClass, IdentityStatus, RiskTier
from app.services.audit_service import AuditService
from app.models.models import AuditCategory

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    identity_class: IdentityClass
    organization: str
    organization_id: Optional[UUID] = None
    source_system: Optional[str] = "manual"
    contract_id: Optional[str] = None
    contract_expires_at: Optional[datetime] = None
    business_justification: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    display_name: Optional[str]
    identity_class: str
    organization: str
    status: str
    risk_tier: str
    current_risk_score: float
    contract_expires_at: Optional[datetime]
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UserStatusUpdate(BaseModel):
    status: IdentityStatus
    reason: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Onboard a new external identity."""
    # Check for duplicate
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User with this email already exists")

    user = User(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        display_name=f"{data.first_name} {data.last_name}",
        identity_class=data.identity_class,
        organization=data.organization,
        organization_id=data.organization_id,
        status=IdentityStatus.active,
        source_system=data.source_system,
        contract_id=data.contract_id,
        contract_expires_at=data.contract_expires_at,
        onboarded_at=datetime.now(timezone.utc),
        created_by=UUID(current_user.user_id) if current_user.user_id else None,
        current_risk_score=50.0,
        risk_tier=RiskTier.medium,
    )
    db.add(user)
    await db.flush()

    # Audit
    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.identity_lifecycle,
        event_type="user_onboarded",
        action="create",
        outcome="success",
        actor_id=UUID(current_user.user_id) if current_user.user_id else None,
        actor_email=current_user.email,
        target_user_id=user.id,
        target_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        payload={"identity_class": data.identity_class.value, "organization": data.organization},
        new_state={"status": "active", "risk_tier": "medium"},
    )

    await db.commit()
    return user


@router.get("/", response_model=List[UserResponse])
async def list_users(
    status: Optional[IdentityStatus] = None,
    identity_class: Optional[IdentityClass] = None,
    risk_tier: Optional[RiskTier] = None,
    search: Optional[str] = Query(None, min_length=2),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List external identities with filtering."""
    query = select(User)
    if status:
        query = query.where(User.status == status)
    if identity_class:
        query = query.where(User.identity_class == identity_class)
    if risk_tier:
        query = query.where(User.risk_tier == risk_tier)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (User.organization.ilike(f"%{search}%"))
        )
    query = query.order_by(User.current_risk_score.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    data: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Suspend, reactivate, or deprovision an external identity."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prev_status = user.status.value
    user.status = data.status
    user.updated_at = datetime.now(timezone.utc)

    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.identity_lifecycle,
        event_type="user_status_changed",
        action="update_status",
        outcome="success",
        actor_id=UUID(current_user.user_id) if current_user.user_id else None,
        actor_email=current_user.email,
        target_user_id=user.id,
        target_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        payload={"reason": data.reason},
        previous_state={"status": prev_status},
        new_state={"status": data.status.value},
    )

    await db.commit()
    return {"id": str(user.id), "status": user.status.value, "updated": True}


@router.delete("/{user_id}/deprovision")
async def deprovision_user(
    user_id: UUID,
    reason: str = Query(..., min_length=5),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Immediately deprovision an external identity and revoke all access."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = IdentityStatus.deprovisioned
    user.updated_at = datetime.now(timezone.utc)

    # Revoke all active roles
    from app.models.models import UserRole
    roles_result = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id).where(UserRole.status == "active")
    )
    active_roles = roles_result.scalars().all()
    for ur in active_roles:
        ur.status = "revoked"
        ur.revoked_at = datetime.now(timezone.utc)
        ur.revoked_by = UUID(current_user.user_id) if current_user.user_id else None
        ur.revocation_reason = f"User deprovisioned: {reason}"

    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.identity_lifecycle,
        event_type="user_deprovisioned",
        action="deprovision",
        outcome="success",
        actor_id=UUID(current_user.user_id) if current_user.user_id else None,
        actor_email=current_user.email,
        target_user_id=user.id,
        target_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        payload={"reason": reason, "roles_revoked": len(active_roles)},
    )

    await db.commit()
    return {"id": str(user.id), "status": "deprovisioned", "roles_revoked": len(active_roles)}


@router.get("/{user_id}/summary")
async def get_user_summary(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full identity summary: user + roles + risk + SoD violations."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.models.models import UserRole, Role, SoDViolation, SoDStatus
    roles_result = await db.execute(
        select(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id)
        .where(UserRole.status == "active")
    )
    user_roles = roles_result.all()

    violations_result = await db.execute(
        select(SoDViolation)
        .where(SoDViolation.user_id == user_id)
        .where(SoDViolation.status == SoDStatus.open)
    )
    violations = violations_result.scalars().all()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.display_name or f"{user.first_name} {user.last_name}",
            "identity_class": user.identity_class.value,
            "organization": user.organization,
            "status": user.status.value,
            "risk_score": float(user.current_risk_score),
            "risk_tier": user.risk_tier.value,
            "contract_expires_at": user.contract_expires_at.isoformat() if user.contract_expires_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "active_roles": [
            {"role_id": str(ur.role_id), "role_name": role.name, "system": role.system_name}
            for ur, role in user_roles
        ],
        "sod_violations": [
            {"violation_id": str(v.id), "severity": v.severity.value, "status": v.status.value}
            for v in violations
        ],
        "risk_alert": float(user.current_risk_score) >= 70.0,
    }
