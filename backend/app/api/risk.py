"""NexusGuard — Risk Engine API"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.services.risk_engine import RiskScoringEngine
from app.models.models import User, RiskScore, RiskTier
from sqlalchemy import select

router = APIRouter()


class RiskEventInput(BaseModel):
    user_id: UUID
    event_type: str
    country: Optional[str] = None
    device_id: Optional[str] = None
    is_new_device: bool = False
    is_bulk_operation: bool = False
    privilege_escalation: bool = False
    resource_sensitivity: Optional[str] = None


@router.post("/score")
async def calculate_risk_score(
    data: RiskEventInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Calculate and update risk score based on an event."""
    engine = RiskScoringEngine(db)
    result = await engine.calculate_risk(data.user_id, data.dict())
    await db.commit()
    return result


@router.get("/users/{user_id}/trend")
async def get_risk_trend(
    user_id: UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get risk score trend for a user over time."""
    engine = RiskScoringEngine(db)
    return {"user_id": str(user_id), "trend": await engine.get_risk_trend(user_id, days)}


@router.get("/high-risk-users")
async def get_high_risk_users(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get all users with high or critical risk scores."""
    result = await db.execute(
        select(User)
        .where(User.risk_tier.in_([RiskTier.high, RiskTier.critical]))
        .where(User.status == "active")
        .order_by(User.current_risk_score.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": f"{u.first_name} {u.last_name}",
            "organization": u.organization,
            "risk_score": float(u.current_risk_score),
            "risk_tier": u.risk_tier.value,
            "identity_class": u.identity_class.value,
        }
        for u in users
    ]
