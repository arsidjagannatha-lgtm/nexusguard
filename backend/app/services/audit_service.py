"""
NexusGuard — Tamper-Evident Audit Service
Hash-chained audit log ensuring integrity and non-repudiation
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.models import AuditEvent, AuditCategory


class AuditService:
    """
    Tamper-evident audit logging using SHA-256 hash chains.
    Each event contains the hash of the previous event, creating
    an immutable chain detectable against tampering.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._genesis_hash = "0" * 64  # Hash of genesis (no previous event)

    async def log(
        self,
        category: AuditCategory,
        event_type: str,
        action: str,
        outcome: str,
        actor_id: Optional[UUID] = None,
        actor_email: Optional[str] = None,
        target_user_id: Optional[UUID] = None,
        target_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        payload: Optional[dict] = None,
        previous_state: Optional[dict] = None,
        new_state: Optional[dict] = None,
    ) -> AuditEvent:
        """Create a new tamper-evident audit event."""
        prev_hash = await self._get_last_hash()

        # Build deterministic content for hashing
        content = {
            "category": category.value,
            "event_type": event_type,
            "action": action,
            "outcome": outcome,
            "actor_id": str(actor_id) if actor_id else None,
            "actor_email": actor_email,
            "target_user_id": str(target_user_id) if target_user_id else None,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload or {},
            "previous_state": previous_state or {},
            "new_state": new_state or {},
            "prev_hash": prev_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        event_hash = self._hash(content)

        event = AuditEvent(
            category=category,
            event_type=event_type,
            actor_id=actor_id,
            actor_email=actor_email,
            target_user_id=target_user_id,
            target_email=target_email,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            ip_address=ip_address,
            payload=payload or {},
            previous_state=previous_state or {},
            new_state=new_state or {},
            event_hash=event_hash,
            prev_hash=prev_hash,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def verify_chain_integrity(
        self,
        from_sequence: Optional[int] = None,
        limit: int = 1000,
    ) -> dict:
        """
        Verify hash chain integrity. Returns any broken links.
        Use this for tamper detection audits.
        """
        query = select(AuditEvent).order_by(AuditEvent.sequence_num.asc()).limit(limit)
        if from_sequence:
            query = query.where(AuditEvent.sequence_num >= from_sequence)

        result = await self.db.execute(query)
        events = result.scalars().all()

        broken_links = []
        prev_hash = self._genesis_hash

        for event in events:
            if event.prev_hash != prev_hash and event.sequence_num != 1:
                broken_links.append({
                    "sequence_num": event.sequence_num,
                    "event_id": str(event.id),
                    "expected_prev_hash": prev_hash,
                    "actual_prev_hash": event.prev_hash,
                    "tamper_detected": True,
                })
            prev_hash = event.event_hash

        return {
            "total_events_checked": len(events),
            "chain_valid": len(broken_links) == 0,
            "broken_links": broken_links,
            "integrity_status": "VALID" if not broken_links else "COMPROMISED",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_events(
        self,
        category: Optional[AuditCategory] = None,
        actor_id: Optional[UUID] = None,
        target_user_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        query = select(AuditEvent).order_by(AuditEvent.created_at.desc())
        if category:
            query = query.where(AuditEvent.category == category)
        if actor_id:
            query = query.where(AuditEvent.actor_id == actor_id)
        if target_user_id:
            query = query.where(AuditEvent.target_user_id == target_user_id)

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        events = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "sequence_num": e.sequence_num,
                "category": e.category.value,
                "event_type": e.event_type,
                "action": e.action,
                "outcome": e.outcome,
                "actor_email": e.actor_email,
                "target_email": e.target_email,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "payload": e.payload,
                "event_hash": e.event_hash[:16] + "...",  # Truncated for display
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

    async def _get_last_hash(self) -> str:
        result = await self.db.execute(
            select(AuditEvent.event_hash)
            .order_by(AuditEvent.sequence_num.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row if row else self._genesis_hash

    def _hash(self, content: dict) -> str:
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
