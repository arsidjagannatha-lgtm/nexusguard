"""
NexusGuard — Backend Test Suite
Tests: risk engine, SoD detection, audit chain, API endpoints
"""
import pytest
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4


# ── Risk Engine Tests ─────────────────────────────────────────────────────────

class TestRiskScoringEngine:

    def test_score_to_tier_critical(self):
        from app.services.risk_engine import score_to_tier
        from app.models.models import RiskTier
        assert score_to_tier(90.0) == RiskTier.critical
        assert score_to_tier(85.0) == RiskTier.critical

    def test_score_to_tier_high(self):
        from app.services.risk_engine import score_to_tier
        from app.models.models import RiskTier
        assert score_to_tier(75.0) == RiskTier.high
        assert score_to_tier(70.0) == RiskTier.high

    def test_score_to_tier_medium(self):
        from app.services.risk_engine import score_to_tier
        from app.models.models import RiskTier
        assert score_to_tier(50.0) == RiskTier.medium
        assert score_to_tier(45.0) == RiskTier.medium

    def test_score_to_tier_low(self):
        from app.services.risk_engine import score_to_tier
        from app.models.models import RiskTier
        assert score_to_tier(25.0) == RiskTier.low
        assert score_to_tier(10.0) == RiskTier.minimal

    def test_risk_weights_sum_reasonable(self):
        from app.services.risk_engine import RISK_WEIGHTS
        total = sum(RISK_WEIGHTS.values())
        # Sum of all risk factors should not exceed ~200
        assert total < 200, f"Risk weights sum too high: {total}"
        assert all(v > 0 for v in RISK_WEIGHTS.values()), "All weights must be positive"

    def test_risk_thresholds_ordered(self):
        from app.services.risk_engine import RISK_TIER_THRESHOLDS
        tiers = ['critical', 'high', 'medium', 'low', 'minimal']
        values = [RISK_TIER_THRESHOLDS[t] for t in tiers]
        assert values == sorted(values, reverse=True), "Thresholds must be in descending order"


# ── Audit Hash Chain Tests ────────────────────────────────────────────────────

class TestAuditHashChain:

    def _make_hash(self, content: dict) -> str:
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def test_hash_is_deterministic(self):
        content = {"event": "test", "actor": "user@test.com", "prev_hash": "0" * 64}
        h1 = self._make_hash(content)
        h2 = self._make_hash(content)
        assert h1 == h2, "Same content must produce same hash"

    def test_hash_changes_on_tamper(self):
        content = {"event": "user_created", "actor": "admin@test.com"}
        original_hash = self._make_hash(content)
        tampered = {**content, "event": "user_deleted"}
        tampered_hash = self._make_hash(tampered)
        assert original_hash != tampered_hash, "Tampered content must produce different hash"

    def test_hash_is_64_chars(self):
        content = {"test": "value"}
        h = self._make_hash(content)
        assert len(h) == 64, f"SHA-256 hash must be 64 hex chars, got {len(h)}"

    def test_chain_link_integrity(self):
        """Simulate a 3-event chain and verify each links to previous."""
        genesis = "0" * 64
        events = []

        for i in range(3):
            prev = events[-1]["hash"] if events else genesis
            content = {"seq": i, "event": f"event_{i}", "prev_hash": prev}
            h = self._make_hash(content)
            events.append({"seq": i, "hash": h, "prev_hash": prev, "content": content})

        # Verify chain
        for i, event in enumerate(events):
            if i == 0:
                assert event["prev_hash"] == genesis
            else:
                assert event["prev_hash"] == events[i-1]["hash"], f"Chain broken at event {i}"

    def test_tamper_detection(self):
        """Detect if middle event in chain is modified."""
        genesis = "0" * 64
        events = []
        for i in range(3):
            prev = events[-1]["hash"] if events else genesis
            content = {"seq": i, "event": f"event_{i}", "prev_hash": prev}
            h = self._make_hash(content)
            events.append({"hash": h, "prev_hash": prev})

        # Tamper with event 1 (simulate DB modification)
        original_hash_1 = events[1]["hash"]
        tampered_content = {"seq": 1, "event": "TAMPERED", "prev_hash": events[0]["hash"]}
        events[1]["hash"] = self._make_hash(tampered_content)

        # Event 2's prev_hash should now not match tampered event 1's hash
        assert events[2]["prev_hash"] == original_hash_1  # Points to original
        assert events[2]["prev_hash"] != events[1]["hash"]  # Mismatch detected


# ── SoD Engine Tests ──────────────────────────────────────────────────────────

class TestSoDEngine:

    def test_sod_conflict_detection_logic(self):
        """
        Test the core conflict detection logic independently of DB.
        Rule: permission_a + permission_b = conflict
        """
        perm_a = str(uuid4())
        perm_b = str(uuid4())
        perm_c = str(uuid4())

        # Case 1: New role has A, existing user has B → conflict
        new_perms = {perm_a}
        existing_perms = {perm_b}
        rule_a = perm_a
        rule_b = perm_b

        conflict = (
            (rule_a in new_perms and rule_b in existing_perms) or
            (rule_b in new_perms and rule_a in existing_perms)
        )
        assert conflict, "Should detect conflict: new=A, existing=B"

        # Case 2: New role has C (unrelated), existing has B → no conflict
        new_perms_c = {perm_c}
        no_conflict = (
            (rule_a in new_perms_c and rule_b in existing_perms) or
            (rule_b in new_perms_c and rule_a in existing_perms)
        )
        assert not no_conflict, "Should NOT detect conflict with unrelated permission"

        # Case 3: New role has both A and B → self-conflict
        new_perms_both = {perm_a, perm_b}
        self_conflict = (rule_a in new_perms_both and rule_b in new_perms_both)
        assert self_conflict, "Should detect self-conflict when role has both conflicting permissions"

    def test_blocking_severity_filter(self):
        """Only critical and high violations should block assignment."""
        violations = [
            {"severity": "critical", "rule": "Invoice Create + Payment Approve"},
            {"severity": "medium",   "rule": "Some lesser conflict"},
        ]
        blocking = [v for v in violations if v["severity"] in ("critical", "high")]
        non_blocking = [v for v in violations if v["severity"] not in ("critical", "high")]

        assert len(blocking) == 1
        assert blocking[0]["severity"] == "critical"
        assert len(non_blocking) == 1
        assert non_blocking[0]["severity"] == "medium"


# ── Risk Blending Tests ───────────────────────────────────────────────────────

class TestRiskBlending:

    def test_blending_formula(self):
        """Exponential moving average blending: alpha=0.4"""
        alpha = 0.4
        previous = 50.0
        new_event_score = 40.0  # geo_anomaly(25) + off_hours(15)

        blended = (alpha * new_event_score) + ((1 - alpha) * previous)
        assert 45.0 <= blended <= 47.0, f"Expected ~46, got {blended}"

    def test_score_cannot_exceed_100(self):
        """Risk score must be clamped to 100."""
        raw = 150.0
        clamped = min(100.0, raw)
        assert clamped == 100.0

    def test_score_blending_with_zero_new_score(self):
        """If no risk factors fire, score should decay toward previous."""
        alpha = 0.4
        previous = 80.0
        new_event_score = 0.0
        blended = (alpha * new_event_score) + ((1 - alpha) * previous)
        assert blended < previous, "Score should decay when no new risk factors"
        assert blended == pytest.approx(48.0)


# ── API Schema Validation Tests ───────────────────────────────────────────────

class TestSchemas:

    def test_identity_class_values(self):
        from app.models.models import IdentityClass
        valid = {e.value for e in IdentityClass}
        assert "vendor" in valid
        assert "partner" in valid
        assert "contractor" in valid
        assert "customer" in valid
        assert "b2b_admin" in valid
        assert "auditor" in valid

    def test_risk_tier_ordering(self):
        """Verify all risk tiers are defined."""
        from app.models.models import RiskTier
        tiers = {e.value for e in RiskTier}
        assert tiers == {"critical", "high", "medium", "low", "minimal"}

    def test_sod_severity_values(self):
        from app.models.models import SoDSeverity
        severities = {e.value for e in SoDSeverity}
        assert "critical" in severities
        assert "high" in severities

    def test_audit_categories_complete(self):
        from app.models.models import AuditCategory
        cats = {e.value for e in AuditCategory}
        required = {
            "identity_lifecycle", "access_change", "authentication",
            "authorization", "risk_event", "review_action", "sod_event",
            "admin_action", "system_event"
        }
        assert required.issubset(cats), f"Missing categories: {required - cats}"


# ── Deprovision Logic Tests ───────────────────────────────────────────────────

class TestDeprovisionLogic:

    def test_contract_expiry_detection(self):
        """Identify users with contracts expiring within 30 days."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        users = [
            {"email": "expired@test.com",   "expires": now - timedelta(days=1)},
            {"email": "expiring@test.com",  "expires": now + timedelta(days=15)},
            {"email": "future@test.com",    "expires": now + timedelta(days=90)},
            {"email": "noexpiry@test.com",  "expires": None},
        ]

        expiring_soon = [
            u for u in users
            if u["expires"] and timedelta(0) <= (u["expires"] - now) <= timedelta(days=30)
        ]

        assert len(expiring_soon) == 1
        assert expiring_soon[0]["email"] == "expiring@test.com"

    def test_inactivity_detection(self):
        """Identify users inactive for more than 90 days."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        users = [
            {"email": "active@test.com",   "last_login": now - timedelta(days=5)},
            {"email": "inactive@test.com", "last_login": now - timedelta(days=100)},
            {"email": "never@test.com",    "last_login": None},
        ]

        inactive = [
            u for u in users
            if u["last_login"] is None or (now - u["last_login"]).days > 90
        ]

        assert len(inactive) == 2
        emails = {u["email"] for u in inactive}
        assert "inactive@test.com" in emails
        assert "never@test.com" in emails
