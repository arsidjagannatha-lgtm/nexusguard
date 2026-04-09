"""
NexusGuard — Dynamic Risk Scoring Engine
Behavioral risk scoring for external identities
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID
import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.models import User, RiskScore, RiskTier, AuditEvent, AuditCategory
from app.core.config import settings


# ── Risk Factor Weights ───────────────────────────────────────────────────────

RISK_WEIGHTS = {
    "geo_anomaly":            25.0,   # Login from atypical country
    "off_hours_access":       15.0,   # Access outside normal hours
    "new_device":             12.0,   # Unrecognized device fingerprint
    "mfa_failure":            20.0,   # Failed MFA attempt
    "bulk_operation":         18.0,   # High-volume data operation
    "privilege_escalation":   30.0,   # Accessed higher-privilege resource
    "failed_login_burst":     22.0,   # Multiple failed logins in window
    "contract_near_expiry":    8.0,   # Contract expiring within 30 days
    "sensitive_data_access":  10.0,   # Accessed PII/sensitive resource
    "concurrent_sessions":    12.0,   # Multiple active sessions
    "rapid_permission_use":   15.0,   # Used all permissions within short window
    "org_risk_inheritance":   10.0,   # From high-risk organization
}

RISK_TIER_THRESHOLDS = {
    "critical": 85.0,
    "high":     70.0,
    "medium":   45.0,
    "low":      20.0,
    "minimal":  0.0,
}


def score_to_tier(score: float) -> RiskTier:
    if score >= RISK_TIER_THRESHOLDS["critical"]:
        return RiskTier.critical
    elif score >= RISK_TIER_THRESHOLDS["high"]:
        return RiskTier.high
    elif score >= RISK_TIER_THRESHOLDS["medium"]:
        return RiskTier.medium
    elif score >= RISK_TIER_THRESHOLDS["low"]:
        return RiskTier.low
    return RiskTier.minimal


class RiskScoringEngine:
    """
    Behavioral risk scoring engine for external identities.
    Evaluates contextual signals and computes a risk score 0-100.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_risk(
        self,
        user_id: UUID,
        event_context: dict,
    ) -> dict:
        """
        Calculate risk score for a user based on an incoming event + behavioral baseline.
        Returns: {score, tier, factors, delta}
        """
        user = await self.db.get(User, user_id)
        if not user:
            return {"score": 100.0, "tier": "critical", "factors": ["user_not_found"], "delta": 0}

        previous_score = float(user.current_risk_score or 50.0)
        factors = {}
        total_risk = 0.0

        # ── Factor: Geographic Anomaly ──
        if event_context.get("country"):
            is_geo_anomaly = await self._check_geo_anomaly(
                user_id, event_context["country"]
            )
            if is_geo_anomaly:
                factors["geo_anomaly"] = RISK_WEIGHTS["geo_anomaly"]
                total_risk += RISK_WEIGHTS["geo_anomaly"]

        # ── Factor: Off-Hours Access ──
        current_hour = datetime.now(timezone.utc).hour
        if current_hour < 6 or current_hour > 22:
            factors["off_hours_access"] = RISK_WEIGHTS["off_hours_access"]
            total_risk += RISK_WEIGHTS["off_hours_access"]

        # ── Factor: New Device ──
        if event_context.get("device_id") and event_context.get("is_new_device"):
            factors["new_device"] = RISK_WEIGHTS["new_device"]
            total_risk += RISK_WEIGHTS["new_device"]

        # ── Factor: MFA Failure ──
        if event_context.get("event_type") == "mfa_failure":
            factors["mfa_failure"] = RISK_WEIGHTS["mfa_failure"]
            total_risk += RISK_WEIGHTS["mfa_failure"]

        # ── Factor: Bulk Operation ──
        if event_context.get("is_bulk_operation"):
            factors["bulk_operation"] = RISK_WEIGHTS["bulk_operation"]
            total_risk += RISK_WEIGHTS["bulk_operation"]

        # ── Factor: Privilege Escalation ──
        if event_context.get("privilege_escalation"):
            factors["privilege_escalation"] = RISK_WEIGHTS["privilege_escalation"]
            total_risk += RISK_WEIGHTS["privilege_escalation"]

        # ── Factor: Contract Near Expiry ──
        if user.contract_expires_at:
            days_to_expiry = (user.contract_expires_at - datetime.now(timezone.utc)).days
            if 0 < days_to_expiry <= 30:
                factors["contract_near_expiry"] = RISK_WEIGHTS["contract_near_expiry"]
                total_risk += RISK_WEIGHTS["contract_near_expiry"]

        # ── Factor: Sensitive Data Access ──
        if event_context.get("resource_sensitivity") in ("high", "critical"):
            factors["sensitive_data_access"] = RISK_WEIGHTS["sensitive_data_access"]
            total_risk += RISK_WEIGHTS["sensitive_data_access"]

        # ── Factor: Organization Risk Inheritance ──
        if user.risk_tier in (RiskTier.high, RiskTier.critical):
            factors["org_risk_inheritance"] = RISK_WEIGHTS["org_risk_inheritance"]
            total_risk += RISK_WEIGHTS["org_risk_inheritance"]

        # ── Blend with previous score (exponential moving avg) ──
        alpha = 0.4  # Weight for new event vs historical
        blended_score = min(100.0, (alpha * total_risk) + ((1 - alpha) * previous_score))
        blended_score = round(blended_score, 2)

        tier = score_to_tier(blended_score)
        delta = round(blended_score - previous_score, 2)

        # ── Persist risk score ──
        risk_record = RiskScore(
            user_id=user_id,
            score=Decimal(str(blended_score)),
            previous_score=Decimal(str(previous_score)),
            score_delta=Decimal(str(delta)),
            risk_tier=tier,
            contributing_factors=factors,
            triggered_by=event_context.get("event_type"),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(risk_record)

        # ── Update user's current score ──
        user.current_risk_score = Decimal(str(blended_score))
        user.risk_tier = tier
        user.last_risk_calc = datetime.now(timezone.utc)
        await self.db.flush()

        return {
            "score": blended_score,
            "tier": tier.value,
            "factors": factors,
            "delta": delta,
            "requires_step_up_auth": blended_score >= settings.RISK_STEP_UP_AUTH_THRESHOLD,
            "requires_session_termination": blended_score >= settings.RISK_CRITICAL_THRESHOLD,
        }

    async def _check_geo_anomaly(self, user_id: UUID, country: str) -> bool:
        """Check if country is outside user's typical access countries."""
        # In production: query risk_baselines table for typical_countries
        # For demo: flag if not US or IN (configurable per user)
        TYPICAL_COUNTRIES = {"US", "IN", "GB", "DE", "CA"}
        return country.upper() not in TYPICAL_COUNTRIES

    async def get_risk_trend(self, user_id: UUID, days: int = 30) -> list:
        """Return risk score history for trending charts."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(RiskScore)
            .where(RiskScore.user_id == user_id)
            .where(RiskScore.calculated_at >= cutoff)
            .order_by(RiskScore.calculated_at.asc())
        )
        scores = result.scalars().all()
        return [
            {
                "date": s.calculated_at.isoformat(),
                "score": float(s.score),
                "tier": s.risk_tier.value,
                "factors": s.contributing_factors,
            }
            for s in scores
        ]
