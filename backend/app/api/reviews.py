"""NexusGuard — Access Reviews API"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.models.models import ReviewCampaign, ReviewItem, ReviewDecision, User, UserRole, AuditCategory
from app.services.audit_service import AuditService

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    campaign_type: str = "quarterly"
    start_date: datetime
    due_date: datetime
    compliance_standard: Optional[str] = None
    scope: Optional[dict] = None


class ReviewDecisionInput(BaseModel):
    decision: ReviewDecision
    justification: str


@router.post("/campaigns", status_code=201)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Launch a new access review campaign."""
    actor_id = UUID(current_user.user_id) if current_user.user_id else None

    campaign = ReviewCampaign(
        name=data.name,
        description=data.description,
        campaign_type=data.campaign_type,
        start_date=data.start_date,
        due_date=data.due_date,
        compliance_standard=data.compliance_standard,
        scope=data.scope or {},
        created_by=actor_id,
        status="active",
    )
    db.add(campaign)
    await db.flush()

    # Auto-generate review items for all active users
    users_result = await db.execute(
        select(User).where(User.status == "active")
    )
    users = users_result.scalars().all()

    item_count = 0
    for user in users:
        roles_result = await db.execute(
            select(UserRole).where(UserRole.user_id == user.id).where(UserRole.status == "active")
        )
        user_roles = roles_result.scalars().all()
        for ur in user_roles:
            item = ReviewItem(
                campaign_id=campaign.id,
                user_id=user.id,
                role_id=ur.role_id,
                reviewer_id=actor_id or user.id,  # Default: self-review (override in prod)
                risk_score_at_review=user.current_risk_score,
            )
            db.add(item)
            item_count += 1

    campaign.total_items = item_count

    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.review_action,
        event_type="campaign_created",
        action="create",
        outcome="success",
        actor_id=actor_id,
        actor_email=current_user.email,
        resource_type="review_campaign",
        resource_id=str(campaign.id),
        payload={"name": data.name, "total_items": item_count},
    )

    await db.commit()
    return {"campaign_id": str(campaign.id), "status": "active", "total_items": item_count}


@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ReviewCampaign).order_by(ReviewCampaign.created_at.desc())
    )
    campaigns = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "status": c.status,
            "campaign_type": c.campaign_type,
            "due_date": c.due_date.isoformat(),
            "total_items": c.total_items,
            "certified_count": c.certified_count,
            "revoked_count": c.revoked_count,
            "completion_rate": float(c.completion_rate or 0),
            "compliance_standard": c.compliance_standard,
        }
        for c in campaigns
    ]


@router.get("/campaigns/{campaign_id}/items")
async def get_campaign_items(
    campaign_id: UUID,
    decision: Optional[ReviewDecision] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = select(ReviewItem).where(ReviewItem.campaign_id == campaign_id)
    if decision:
        query = query.where(ReviewItem.decision == decision)
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "user_id": str(i.user_id),
            "role_id": str(i.role_id) if i.role_id else None,
            "reviewer_id": str(i.reviewer_id),
            "decision": i.decision.value,
            "risk_score_at_review": float(i.risk_score_at_review or 0),
            "decision_at": i.decision_at.isoformat() if i.decision_at else None,
            "justification": i.justification,
        }
        for i in items
    ]


@router.post("/items/{item_id}/decide")
async def decide_review_item(
    item_id: UUID,
    data: ReviewDecisionInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Certify or revoke access for a review item."""
    item = await db.get(ReviewItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.decision != ReviewDecision.pending:
        raise HTTPException(status_code=409, detail="Review item already decided")

    actor_id = UUID(current_user.user_id) if current_user.user_id else None
    item.decision = data.decision
    item.decision_at = datetime.now(timezone.utc)
    item.decision_by = actor_id
    item.justification = data.justification

    # If revoked — queue deprovisioning of this specific role
    if data.decision == ReviewDecision.revoked and item.role_id:
        roles_result = await db.execute(
            select(UserRole)
            .where(UserRole.user_id == item.user_id)
            .where(UserRole.role_id == item.role_id)
            .where(UserRole.status == "active")
        )
        user_role = roles_result.scalar_one_or_none()
        if user_role:
            user_role.status = "revoked"
            user_role.revoked_at = datetime.now(timezone.utc)
            user_role.revoked_by = actor_id
            user_role.revocation_reason = f"UAR revocation: {data.justification}"

    # Update campaign counts
    campaign = await db.get(ReviewCampaign, item.campaign_id)
    if campaign:
        if data.decision == ReviewDecision.certified:
            campaign.certified_count = (campaign.certified_count or 0) + 1
        elif data.decision == ReviewDecision.revoked:
            campaign.revoked_count = (campaign.revoked_count or 0) + 1
        completed = (campaign.certified_count or 0) + (campaign.revoked_count or 0) + (campaign.escalated_count or 0)
        if campaign.total_items:
            campaign.completion_rate = (completed / campaign.total_items) * 100

    audit = AuditService(db)
    await audit.log(
        category=AuditCategory.review_action,
        event_type="review_decision",
        action=data.decision.value,
        outcome="success",
        actor_id=actor_id,
        actor_email=current_user.email,
        target_user_id=item.user_id,
        resource_type="review_item",
        resource_id=str(item_id),
        payload={"decision": data.decision.value, "justification": data.justification},
    )

    await db.commit()
    return {"item_id": str(item_id), "decision": data.decision.value}
