"""NexusGuard — Dashboard API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.models.models import (
    User, IdentityStatus, RiskTier, SoDViolation, SoDStatus,
    ReviewCampaign, AuditEvent
)
from datetime import datetime, timezone, timedelta

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Main dashboard KPI summary."""

    # ── User counts ──
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar()

    active_result = await db.execute(
        select(func.count(User.id)).where(User.status == IdentityStatus.active)
    )
    active_users = active_result.scalar()

    # ── Risk distribution ──
    risk_result = await db.execute(
        select(User.risk_tier, func.count(User.id).label("count"))
        .where(User.status == IdentityStatus.active)
        .group_by(User.risk_tier)
    )
    risk_distribution = {row.risk_tier.value: row.count for row in risk_result}

    # ── SoD violations ──
    sod_result = await db.execute(
        select(func.count(SoDViolation.id))
        .where(SoDViolation.status == SoDStatus.open)
    )
    open_sod = sod_result.scalar()

    critical_sod_result = await db.execute(
        select(func.count(SoDViolation.id))
        .where(SoDViolation.status == SoDStatus.open)
        .where(SoDViolation.severity == "critical")
    )
    critical_sod = critical_sod_result.scalar()

    # ── Active campaigns ──
    campaigns_result = await db.execute(
        select(func.count(ReviewCampaign.id)).where(ReviewCampaign.status == "active")
    )
    active_campaigns = campaigns_result.scalar()

    # ── Contract expiring soon (30 days) ──
    soon = datetime.now(timezone.utc) + timedelta(days=30)
    expiring_result = await db.execute(
        select(func.count(User.id))
        .where(User.status == IdentityStatus.active)
        .where(User.contract_expires_at <= soon)
        .where(User.contract_expires_at >= datetime.now(timezone.utc))
    )
    expiring_soon = expiring_result.scalar()

    # ── Recent audit events (last 24h) ──
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    audit_result = await db.execute(
        select(func.count(AuditEvent.id)).where(AuditEvent.created_at >= cutoff)
    )
    recent_audit_count = audit_result.scalar()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "expiring_contracts": expiring_soon,
        },
        "risk": {
            "distribution": risk_distribution,
            "critical": risk_distribution.get("critical", 0),
            "high": risk_distribution.get("high", 0),
            "medium": risk_distribution.get("medium", 0),
            "low": risk_distribution.get("low", 0) + risk_distribution.get("minimal", 0),
        },
        "sod": {
            "open_violations": open_sod,
            "critical_violations": critical_sod,
        },
        "reviews": {
            "active_campaigns": active_campaigns,
        },
        "audit": {
            "events_last_24h": recent_audit_count,
        },
    }


@router.get("/identity-breakdown")
async def get_identity_breakdown(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Breakdown of identities by class."""
    result = await db.execute(
        select(User.identity_class, func.count(User.id).label("count"))
        .where(User.status == IdentityStatus.active)
        .group_by(User.identity_class)
    )
    return [{"class": row.identity_class.value, "count": row.count} for row in result]


@router.get("/recent-activity")
async def get_recent_activity(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Recent audit events for activity feed."""
    result = await db.execute(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(20)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "action": e.action,
            "outcome": e.outcome,
            "actor_email": e.actor_email,
            "target_email": e.target_email,
            "category": e.category.value,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/risk-heatmap")
async def get_risk_heatmap(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Risk score data for heatmap visualization."""
    result = await db.execute(
        select(User)
        .where(User.status == IdentityStatus.active)
        .order_by(User.current_risk_score.desc())
        .limit(50)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "name": f"{u.first_name} {u.last_name}",
            "email": u.email,
            "organization": u.organization,
            "identity_class": u.identity_class.value,
            "risk_score": float(u.current_risk_score),
            "risk_tier": u.risk_tier.value,
        }
        for u in users
    ]
