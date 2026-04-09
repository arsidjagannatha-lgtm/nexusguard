-- NexusGuard PostgreSQL Schema
-- External Identity Governance Platform
-- Version: 1.0.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- IDENTITY LAYER
-- ─────────────────────────────────────────────────────────────

CREATE TYPE identity_class AS ENUM ('vendor', 'partner', 'contractor', 'customer', 'b2b_admin', 'auditor');
CREATE TYPE identity_status AS ENUM ('pending', 'active', 'suspended', 'deprovisioned', 'expired');
CREATE TYPE risk_tier AS ENUM ('critical', 'high', 'medium', 'low', 'minimal');

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id         VARCHAR(255) UNIQUE,           -- ID in source system
    email               VARCHAR(255) UNIQUE NOT NULL,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    display_name        VARCHAR(255),
    identity_class      identity_class NOT NULL,
    organization        VARCHAR(255) NOT NULL,          -- Vendor/partner org name
    organization_id     UUID,                           -- FK to organizations
    status              identity_status NOT NULL DEFAULT 'pending',
    risk_tier           risk_tier DEFAULT 'medium',
    current_risk_score  DECIMAL(5,2) DEFAULT 50.0,     -- 0.0 - 100.0
    source_system       VARCHAR(100),                   -- salesforce, servicenow, manual
    contract_id         VARCHAR(255),                   -- Contract reference
    contract_expires_at TIMESTAMPTZ,
    onboarded_at        TIMESTAMPTZ,
    last_login          TIMESTAMPTZ,
    last_risk_calc      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    metadata            JSONB DEFAULT '{}'
);

CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(100),                       -- vendor, partner, customer
    domain          VARCHAR(255),
    country         VARCHAR(10),
    risk_tier       risk_tier DEFAULT 'medium',
    baa_executed    BOOLEAN DEFAULT FALSE,              -- HIPAA BAA
    pci_scoped      BOOLEAN DEFAULT FALSE,
    gdpr_dpa        BOOLEAN DEFAULT FALSE,              -- GDPR DPA executed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

ALTER TABLE users ADD CONSTRAINT fk_users_org 
    FOREIGN KEY (organization_id) REFERENCES organizations(id);

-- ─────────────────────────────────────────────────────────────
-- RBAC LAYER
-- ─────────────────────────────────────────────────────────────

CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255),
    description     TEXT,
    scope           VARCHAR(100) DEFAULT 'global',     -- global, system, application
    system_name     VARCHAR(100),                       -- Which system this role is in
    risk_level      risk_tier DEFAULT 'low',
    is_sensitive    BOOLEAN DEFAULT FALSE,
    is_privileged   BOOLEAN DEFAULT FALSE,
    owner_id        UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

CREATE TABLE permissions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255),
    description     TEXT,
    resource        VARCHAR(255) NOT NULL,              -- e.g., "invoice", "payment"
    action          VARCHAR(100) NOT NULL,              -- e.g., "create", "approve", "read"
    system_name     VARCHAR(100),
    is_sensitive    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by      UUID,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    assigned_by     UUID,
    business_justification TEXT,
    status          VARCHAR(50) DEFAULT 'active',       -- active, suspended, expired, revoked
    revoked_at      TIMESTAMPTZ,
    revoked_by      UUID,
    revocation_reason TEXT
);

CREATE UNIQUE INDEX idx_user_roles_active 
    ON user_roles(user_id, role_id) 
    WHERE status = 'active';

-- ─────────────────────────────────────────────────────────────
-- SOD ENGINE
-- ─────────────────────────────────────────────────────────────

CREATE TYPE sod_severity AS ENUM ('critical', 'high', 'medium', 'low');
CREATE TYPE sod_status AS ENUM ('open', 'mitigated', 'accepted', 'false_positive', 'remediated');

CREATE TABLE sod_rules (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    permission_a_id     UUID NOT NULL REFERENCES permissions(id),
    permission_b_id     UUID NOT NULL REFERENCES permissions(id),
    severity            sod_severity NOT NULL DEFAULT 'high',
    compliance_control  VARCHAR(100),                   -- SOX-CC6.1, PCI-DSS-7.1, etc.
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID
);

CREATE TABLE sod_violations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id),
    sod_rule_id         UUID NOT NULL REFERENCES sod_rules(id),
    permission_a_id     UUID NOT NULL REFERENCES permissions(id),
    permission_b_id     UUID NOT NULL REFERENCES permissions(id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              sod_status NOT NULL DEFAULT 'open',
    severity            sod_severity NOT NULL,
    remediation_action  TEXT,
    remediated_at       TIMESTAMPTZ,
    remediated_by       UUID,
    mitigating_control  TEXT,
    accepted_by         UUID,
    accepted_at         TIMESTAMPTZ,
    acceptance_reason   TEXT,
    review_due_date     TIMESTAMPTZ
);

-- ─────────────────────────────────────────────────────────────
-- RISK SCORING ENGINE
-- ─────────────────────────────────────────────────────────────

CREATE TYPE event_type AS ENUM (
    'login_success', 'login_failure', 'mfa_success', 'mfa_failure',
    'access_granted', 'access_denied', 'session_created', 'session_terminated',
    'data_export', 'admin_action', 'api_call', 'privilege_escalation',
    'off_hours_access', 'geo_anomaly', 'new_device', 'bulk_operation'
);

CREATE TABLE access_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    event_type      event_type NOT NULL,
    resource        VARCHAR(255),
    action          VARCHAR(100),
    ip_address      INET,
    country         VARCHAR(10),
    city            VARCHAR(100),
    user_agent      TEXT,
    device_id       VARCHAR(255),
    session_id      VARCHAR(255),
    risk_score      DECIMAL(5,2),
    risk_factors    JSONB DEFAULT '[]',                -- Array of contributing factors
    success         BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for access_logs
CREATE TABLE access_logs_2025_01 PARTITION OF access_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE access_logs_2025_q2 PARTITION OF access_logs
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE access_logs_2025_q3 PARTITION OF access_logs
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE access_logs_2025_q4 PARTITION OF access_logs
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE access_logs_2026_q1 PARTITION OF access_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE access_logs_default PARTITION OF access_logs DEFAULT;

CREATE TABLE risk_scores (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id),
    score               DECIMAL(5,2) NOT NULL,          -- 0.0 - 100.0
    previous_score      DECIMAL(5,2),
    score_delta         DECIMAL(5,2),
    risk_tier           risk_tier NOT NULL,
    contributing_factors JSONB NOT NULL DEFAULT '{}',
    calculated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until         TIMESTAMPTZ,
    triggered_by        event_type,
    triggering_log_id   UUID
);

CREATE TABLE risk_baselines (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) UNIQUE,
    avg_login_hour      DECIMAL(4,2),                   -- Average login hour (0-23)
    typical_countries   TEXT[],                         -- e.g., ['US', 'IN']
    typical_devices     TEXT[],
    avg_daily_api_calls INTEGER,
    avg_session_duration INTERVAL,
    last_calculated     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sample_days         INTEGER DEFAULT 30
);

-- ─────────────────────────────────────────────────────────────
-- ACCESS REVIEW (UAR) ENGINE
-- ─────────────────────────────────────────────────────────────

CREATE TYPE campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled');
CREATE TYPE review_decision AS ENUM ('certified', 'revoked', 'escalated', 'pending');

CREATE TABLE review_campaigns (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    status              campaign_status NOT NULL DEFAULT 'draft',
    campaign_type       VARCHAR(100) DEFAULT 'quarterly',  -- quarterly, annual, triggered, ad_hoc
    scope               JSONB DEFAULT '{}',                -- filters: identity_class, org, system
    created_by          UUID NOT NULL,
    start_date          TIMESTAMPTZ NOT NULL,
    due_date            TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ,
    completion_rate     DECIMAL(5,2),                      -- % of reviews completed
    total_items         INTEGER DEFAULT 0,
    certified_count     INTEGER DEFAULT 0,
    revoked_count       INTEGER DEFAULT 0,
    escalated_count     INTEGER DEFAULT 0,
    compliance_standard VARCHAR(100),                      -- SOX, HIPAA, PCI
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE review_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id         UUID NOT NULL REFERENCES review_campaigns(id),
    user_id             UUID NOT NULL REFERENCES users(id),
    role_id             UUID REFERENCES roles(id),
    permission_id       UUID REFERENCES permissions(id),
    reviewer_id         UUID NOT NULL,                     -- who must review
    decision            review_decision DEFAULT 'pending',
    decision_at         TIMESTAMPTZ,
    decision_by         UUID,
    justification       TEXT,
    risk_score_at_review DECIMAL(5,2),
    escalated_to        UUID,
    escalated_at        TIMESTAMPTZ,
    escalation_reason   TEXT,
    reminder_count      INTEGER DEFAULT 0,
    last_reminder_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- AUDIT LAYER (TAMPER-EVIDENT)
-- ─────────────────────────────────────────────────────────────

CREATE TYPE audit_category AS ENUM (
    'identity_lifecycle', 'access_change', 'authentication', 'authorization',
    'risk_event', 'review_action', 'sod_event', 'admin_action', 'system_event'
);

CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sequence_num    BIGSERIAL UNIQUE NOT NULL,            -- monotonic sequence
    category        audit_category NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    actor_id        UUID,                                  -- who performed the action
    actor_email     VARCHAR(255),
    target_user_id  UUID,
    target_email    VARCHAR(255),
    resource_type   VARCHAR(100),
    resource_id     VARCHAR(255),
    action          VARCHAR(100) NOT NULL,
    outcome         VARCHAR(50) NOT NULL,                  -- success, failure, partial
    ip_address      INET,
    payload         JSONB DEFAULT '{}',                    -- action details
    previous_state  JSONB DEFAULT '{}',
    new_state       JSONB DEFAULT '{}',
    event_hash      VARCHAR(64) NOT NULL,                  -- SHA-256 of event content
    prev_hash       VARCHAR(64),                           -- Hash of previous event (chain)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hash chain integrity: each event references previous event hash
-- Tamper detection: recalculate hashes and verify chain integrity

CREATE INDEX idx_audit_events_sequence ON audit_events(sequence_num);
CREATE INDEX idx_audit_events_actor ON audit_events(actor_id);
CREATE INDEX idx_audit_events_target ON audit_events(target_user_id);
CREATE INDEX idx_audit_events_created ON audit_events(created_at);
CREATE INDEX idx_audit_events_category ON audit_events(category);

-- ─────────────────────────────────────────────────────────────
-- DEPROVISION QUEUE
-- ─────────────────────────────────────────────────────────────

CREATE TYPE deprovision_reason AS ENUM (
    'contract_expired', 'uar_revocation', 'risk_triggered', 'manual',
    'sod_violation', 'inactivity', 'organization_offboarding'
);

CREATE TABLE deprovision_queue (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id),
    reason              deprovision_reason NOT NULL,
    triggered_by        VARCHAR(255),                      -- campaign_id, risk_event_id, etc.
    scheduled_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execute_at          TIMESTAMPTZ NOT NULL,               -- when to actually execute
    executed_at         TIMESTAMPTZ,
    status              VARCHAR(50) DEFAULT 'queued',       -- queued, processing, completed, failed
    error_message       TEXT,
    systems_to_deprovision TEXT[],                         -- list of target systems
    completion_evidence JSONB DEFAULT '{}'
);

-- ─────────────────────────────────────────────────────────────
-- INDEXES FOR PERFORMANCE
-- ─────────────────────────────────────────────────────────────

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_identity_class ON users(identity_class);
CREATE INDEX idx_users_risk_tier ON users(risk_tier);
CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_contract_expires ON users(contract_expires_at);

CREATE INDEX idx_access_logs_user ON access_logs(user_id);
CREATE INDEX idx_access_logs_created ON access_logs(created_at);
CREATE INDEX idx_access_logs_event_type ON access_logs(event_type);

CREATE INDEX idx_sod_violations_user ON sod_violations(user_id);
CREATE INDEX idx_sod_violations_status ON sod_violations(status);

CREATE INDEX idx_review_items_campaign ON review_items(campaign_id);
CREATE INDEX idx_review_items_reviewer ON review_items(reviewer_id);
CREATE INDEX idx_review_items_decision ON review_items(decision);

CREATE INDEX idx_risk_scores_user ON risk_scores(user_id);
CREATE INDEX idx_risk_scores_calculated ON risk_scores(calculated_at);

-- ─────────────────────────────────────────────────────────────
-- SAMPLE DATA
-- ─────────────────────────────────────────────────────────────

-- Organizations
INSERT INTO organizations (id, name, type, domain, country, baa_executed, gdpr_dpa) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Acme Consulting', 'vendor', 'acmeconsulting.com', 'US', false, true),
    ('22222222-2222-2222-2222-222222222222', 'TechPartner Inc', 'partner', 'techpartner.io', 'DE', false, true),
    ('33333333-3333-3333-3333-333333333333', 'MedSupply Co', 'vendor', 'medsupply.com', 'US', true, false);

-- Roles
INSERT INTO roles (id, name, display_name, system_name, risk_level, is_sensitive) VALUES
    ('aaaa0001-0001-0001-0001-000000000001', 'vendor_read_only', 'Vendor Read-Only', 'ERP', 'low', false),
    ('aaaa0002-0002-0002-0002-000000000002', 'vendor_data_entry', 'Vendor Data Entry', 'ERP', 'medium', false),
    ('aaaa0003-0003-0003-0003-000000000003', 'invoice_creator', 'Invoice Creator', 'Finance', 'high', true),
    ('aaaa0004-0004-0004-0004-000000000004', 'payment_approver', 'Payment Approver', 'Finance', 'critical', true),
    ('aaaa0005-0005-0005-0005-000000000005', 'partner_admin', 'Partner Admin', 'Portal', 'high', true);

-- Permissions
INSERT INTO permissions (id, name, resource, action, system_name, is_sensitive) VALUES
    ('bbbb0001-0001-0001-0001-000000000001', 'invoice.create', 'invoice', 'create', 'Finance', true),
    ('bbbb0002-0002-0002-0002-000000000002', 'invoice.read', 'invoice', 'read', 'Finance', false),
    ('bbbb0003-0003-0003-0003-000000000003', 'payment.approve', 'payment', 'approve', 'Finance', true),
    ('bbbb0004-0004-0004-0004-000000000004', 'payment.initiate', 'payment', 'initiate', 'Finance', true),
    ('bbbb0005-0005-0005-0005-000000000005', 'user.admin', 'user', 'admin', 'Portal', true);

-- SoD Rules (critical financial SoD)
INSERT INTO sod_rules (id, name, description, permission_a_id, permission_b_id, severity, compliance_control) VALUES
    ('cccc0001-0001-0001-0001-000000000001',
     'Invoice Create + Payment Approve',
     'A user cannot both create invoices and approve payments (classic financial SoD)',
     'bbbb0001-0001-0001-0001-000000000001',
     'bbbb0003-0003-0003-0003-000000000003',
     'critical', 'SOX-CC6.1'),
    ('cccc0002-0002-0002-0002-000000000002',
     'Payment Initiate + Payment Approve',
     'A user cannot both initiate and approve their own payments',
     'bbbb0004-0004-0004-0004-000000000004',
     'bbbb0003-0003-0003-0003-000000000003',
     'critical', 'SOX-CC6.1');
