"""NexusGuard — SQLAlchemy ORM Models"""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Numeric, Integer,
    ForeignKey, Text, ARRAY, Enum as SAEnum, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class IdentityClass(str, enum.Enum):
    vendor = "vendor"
    partner = "partner"
    contractor = "contractor"
    customer = "customer"
    b2b_admin = "b2b_admin"
    auditor = "auditor"


class IdentityStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    deprovisioned = "deprovisioned"
    expired = "expired"


class RiskTier(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    minimal = "minimal"


class SoDSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class SoDStatus(str, enum.Enum):
    open = "open"
    mitigated = "mitigated"
    accepted = "accepted"
    false_positive = "false_positive"
    remediated = "remediated"


class ReviewDecision(str, enum.Enum):
    certified = "certified"
    revoked = "revoked"
    escalated = "escalated"
    pending = "pending"


class AuditCategory(str, enum.Enum):
    identity_lifecycle = "identity_lifecycle"
    access_change = "access_change"
    authentication = "authentication"
    authorization = "authorization"
    risk_event = "risk_event"
    review_action = "review_action"
    sod_event = "sod_event"
    admin_action = "admin_action"
    system_event = "system_event"


# ── Models ────────────────────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(255), nullable=False)
    type            = Column(String(100))
    domain          = Column(String(255))
    country         = Column(String(10))
    risk_tier       = Column(SAEnum(RiskTier), default=RiskTier.medium)
    baa_executed    = Column(Boolean, default=False)
    pci_scoped      = Column(Boolean, default=False)
    gdpr_dpa        = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata_       = Column("metadata", JSONB, default=dict)

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id         = Column(String(255), unique=True)
    email               = Column(String(255), unique=True, nullable=False)
    first_name          = Column(String(100), nullable=False)
    last_name           = Column(String(100), nullable=False)
    display_name        = Column(String(255))
    identity_class      = Column(SAEnum(IdentityClass), nullable=False)
    organization        = Column(String(255), nullable=False)
    organization_id     = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    status              = Column(SAEnum(IdentityStatus), default=IdentityStatus.pending)
    risk_tier           = Column(SAEnum(RiskTier), default=RiskTier.medium)
    current_risk_score  = Column(Numeric(5, 2), default=50.0)
    source_system       = Column(String(100))
    contract_id         = Column(String(255))
    contract_expires_at = Column(DateTime(timezone=True))
    onboarded_at        = Column(DateTime(timezone=True))
    last_login          = Column(DateTime(timezone=True))
    last_risk_calc      = Column(DateTime(timezone=True))
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by          = Column(UUID(as_uuid=True))
    metadata_           = Column("metadata", JSONB, default=dict)

    org                 = relationship("Organization", back_populates="users")
    user_roles          = relationship("UserRole", back_populates="user")
    risk_scores         = relationship("RiskScore", back_populates="user")
    sod_violations      = relationship("SoDViolation", back_populates="user")


class Role(Base):
    __tablename__ = "roles"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(255), nullable=False)
    display_name    = Column(String(255))
    description     = Column(Text)
    scope           = Column(String(100), default="global")
    system_name     = Column(String(100))
    risk_level      = Column(SAEnum(RiskTier), default=RiskTier.low)
    is_sensitive    = Column(Boolean, default=False)
    is_privileged   = Column(Boolean, default=False)
    owner_id        = Column(UUID(as_uuid=True))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    metadata_       = Column("metadata", JSONB, default=dict)

    role_permissions = relationship("RolePermission", back_populates="role")
    user_roles      = relationship("UserRole", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(255), nullable=False)
    display_name    = Column(String(255))
    description     = Column(Text)
    resource        = Column(String(255), nullable=False)
    action          = Column(String(100), nullable=False)
    system_name     = Column(String(100))
    is_sensitive    = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id         = Column(UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True)
    permission_id   = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True)
    granted_at      = Column(DateTime(timezone=True), server_default=func.now())
    granted_by      = Column(UUID(as_uuid=True))

    role            = relationship("Role", back_populates="role_permissions")
    permission      = relationship("Permission", back_populates="role_permissions")


class UserRole(Base):
    __tablename__ = "user_roles"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                 = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id                 = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    assigned_at             = Column(DateTime(timezone=True), server_default=func.now())
    expires_at              = Column(DateTime(timezone=True))
    assigned_by             = Column(UUID(as_uuid=True))
    business_justification  = Column(Text)
    status                  = Column(String(50), default="active")
    revoked_at              = Column(DateTime(timezone=True))
    revoked_by              = Column(UUID(as_uuid=True))
    revocation_reason       = Column(Text)

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")


class SoDRule(Base):
    __tablename__ = "sod_rules"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                = Column(String(255), nullable=False)
    description         = Column(Text)
    permission_a_id     = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    permission_b_id     = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    severity            = Column(SAEnum(SoDSeverity), nullable=False, default=SoDSeverity.high)
    compliance_control  = Column(String(100))
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    created_by          = Column(UUID(as_uuid=True))

    violations = relationship("SoDViolation", back_populates="rule")


class SoDViolation(Base):
    __tablename__ = "sod_violations"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sod_rule_id         = Column(UUID(as_uuid=True), ForeignKey("sod_rules.id"), nullable=False)
    permission_a_id     = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    permission_b_id     = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    detected_at         = Column(DateTime(timezone=True), server_default=func.now())
    status              = Column(SAEnum(SoDStatus), default=SoDStatus.open)
    severity            = Column(SAEnum(SoDSeverity), nullable=False)
    remediation_action  = Column(Text)
    remediated_at       = Column(DateTime(timezone=True))
    remediated_by       = Column(UUID(as_uuid=True))
    mitigating_control  = Column(Text)
    accepted_by         = Column(UUID(as_uuid=True))
    accepted_at         = Column(DateTime(timezone=True))
    acceptance_reason   = Column(Text)

    user = relationship("User", back_populates="sod_violations")
    rule = relationship("SoDRule", back_populates="violations")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                 = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    score                   = Column(Numeric(5, 2), nullable=False)
    previous_score          = Column(Numeric(5, 2))
    score_delta             = Column(Numeric(5, 2))
    risk_tier               = Column(SAEnum(RiskTier), nullable=False)
    contributing_factors    = Column(JSONB, default=dict)
    calculated_at           = Column(DateTime(timezone=True), server_default=func.now())
    valid_until             = Column(DateTime(timezone=True))
    triggered_by            = Column(String(100))

    user = relationship("User", back_populates="risk_scores")


class ReviewCampaign(Base):
    __tablename__ = "review_campaigns"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                = Column(String(255), nullable=False)
    description         = Column(Text)
    status              = Column(String(50), default="draft")
    campaign_type       = Column(String(100), default="quarterly")
    scope               = Column(JSONB, default=dict)
    created_by          = Column(UUID(as_uuid=True), nullable=False)
    start_date          = Column(DateTime(timezone=True), nullable=False)
    due_date            = Column(DateTime(timezone=True), nullable=False)
    completed_at        = Column(DateTime(timezone=True))
    completion_rate     = Column(Numeric(5, 2))
    total_items         = Column(Integer, default=0)
    certified_count     = Column(Integer, default=0)
    revoked_count       = Column(Integer, default=0)
    escalated_count     = Column(Integer, default=0)
    compliance_standard = Column(String(100))
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("ReviewItem", back_populates="campaign")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id             = Column(UUID(as_uuid=True), ForeignKey("review_campaigns.id"), nullable=False)
    user_id                 = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id                 = Column(UUID(as_uuid=True), ForeignKey("roles.id"))
    reviewer_id             = Column(UUID(as_uuid=True), nullable=False)
    decision                = Column(SAEnum(ReviewDecision), default=ReviewDecision.pending)
    decision_at             = Column(DateTime(timezone=True))
    decision_by             = Column(UUID(as_uuid=True))
    justification           = Column(Text)
    risk_score_at_review    = Column(Numeric(5, 2))
    escalated_to            = Column(UUID(as_uuid=True))
    escalated_at            = Column(DateTime(timezone=True))
    reminder_count          = Column(Integer, default=0)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())

    campaign    = relationship("ReviewCampaign", back_populates="items")
    user        = relationship("User")
    role        = relationship("Role")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_num    = Column(BigInteger, unique=True)
    category        = Column(SAEnum(AuditCategory), nullable=False)
    event_type      = Column(String(100), nullable=False)
    actor_id        = Column(UUID(as_uuid=True))
    actor_email     = Column(String(255))
    target_user_id  = Column(UUID(as_uuid=True))
    target_email    = Column(String(255))
    resource_type   = Column(String(100))
    resource_id     = Column(String(255))
    action          = Column(String(100), nullable=False)
    outcome         = Column(String(50), nullable=False)
    ip_address      = Column(INET)
    payload         = Column(JSONB, default=dict)
    previous_state  = Column(JSONB, default=dict)
    new_state       = Column(JSONB, default=dict)
    event_hash      = Column(String(64), nullable=False)
    prev_hash       = Column(String(64))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
