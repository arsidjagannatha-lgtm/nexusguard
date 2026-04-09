"""NexusGuard — Audit API"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.services.audit_service import AuditService
from app.models.models import AuditCategory

router = APIRouter()


@router.get("/events")
async def list_audit_events(
    category: Optional[AuditCategory] = None,
    target_user_id: Optional[UUID] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = AuditService(db)
    return await svc.get_events(
        category=category,
        target_user_id=target_user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/integrity")
async def verify_integrity(
    from_sequence: Optional[int] = None,
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Verify hash chain integrity of the audit log."""
    svc = AuditService(db)
    return await svc.verify_chain_integrity(from_sequence=from_sequence, limit=limit)
