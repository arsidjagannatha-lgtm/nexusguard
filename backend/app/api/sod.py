"""NexusGuard — SoD Engine API"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.services.sod_engine import SoDEngine
from app.models.models import SoDViolation, SoDStatus, SoDRule

router = APIRouter()


class RemediationInput(BaseModel):
    action: str  # accept | remediate | mitigate
    reason: str
    mitigating_control: Optional[str] = None


@router.get("/violations")
async def list_violations(
    status: Optional[SoDStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all SoD violations."""
    query = select(SoDViolation)
    if status:
        query = query.where(SoDViolation.status == status)
    query = query.order_by(SoDViolation.detected_at.desc())
    result = await db.execute(query)
    violations = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "user_id": str(v.user_id),
            "sod_rule_id": str(v.sod_rule_id),
            "severity": v.severity.value,
            "status": v.status.value,
            "detected_at": v.detected_at.isoformat(),
            "remediated_at": v.remediated_at.isoformat() if v.remediated_at else None,
        }
        for v in violations
    ]


@router.get("/violations/summary")
async def violations_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Dashboard summary of SoD violations by severity."""
    engine = SoDEngine(db)
    return await engine.get_violations_summary()


@router.post("/scan/{user_id}")
async def scan_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Run full SoD scan for a specific user."""
    engine = SoDEngine(db)
    violations = await engine.scan_user_violations(user_id)
    await db.commit()
    return {"user_id": str(user_id), "violations_found": len(violations), "violations": violations}


@router.post("/violations/{violation_id}/remediate")
async def remediate_violation(
    violation_id: UUID,
    data: RemediationInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    engine = SoDEngine(db)
    actor_id = UUID(current_user.user_id) if current_user.user_id else None
    result = await engine.remediate_violation(
        violation_id, data.action, actor_id, data.reason, data.mitigating_control
    )
    await db.commit()
    return result


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all SoD rules."""
    result = await db.execute(select(SoDRule).where(SoDRule.is_active == True))
    rules = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "severity": r.severity.value,
            "compliance_control": r.compliance_control,
            "permission_a_id": str(r.permission_a_id),
            "permission_b_id": str(r.permission_b_id),
        }
        for r in rules
    ]
