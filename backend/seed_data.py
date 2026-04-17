#!/usr/bin/env python3
"""
NexusGuard — Realistic Seed Data
=================================
Populates the database with a production-representative IAM scenario:
  - 3 organizations spanning different relationship types and risk tiers
  - 17 atomic permissions across 4 real enterprise systems
  - 12 roles with system_name tags (ERP, Finance, HR, CRM, Portal)
  - 4 SoD rules tied to actual compliance controls (SOX, HIPAA)
  - 8 users across all 5 external identity classes
  - Intentional SoD violations on 2 users (for demo / dashboard value)
  - 1 expired contract user (triggers lifecycle warning)
  - 1 access review campaign seeded with review items

WHY DIRECT SQLALCHEMY (not HTTP):
  The seed requires creating organizations, roles, permissions, and SoD rules —
  none of which have API endpoints yet (Days 8–21 build those). Using SQLAlchemy
  directly is also faster, works without the API server running, and lets us
  intentionally bypass the SoD pre-check to seed demonstration violations.

IDEMPOTENCY:
  The script checks whether seed data already exists before inserting. Running
  it a second time produces no duplicate rows and a clear "already seeded" message.

Usage:
  cd backend
  python seed_data.py                        # default: localhost:5432
  DATABASE_URL=postgresql+asyncpg://... python seed_data.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ── path / env bootstrap ─────────────────────────────────────────────────────
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import Base
from app.models.models import (
    Organization, User, Role, Permission, RolePermission, UserRole,
    SoDRule, SoDViolation, ReviewCampaign, ReviewItem,
    IdentityClass, IdentityStatus, RiskTier, SoDSeverity, SoDStatus,
    ReviewDecision, AuditCategory, AuditEvent,
)
from app.services.sod_engine import SoDEngine
from app.services.audit_service import AuditService

# ── well-known UUIDs (stable across re-runs) ─────────────────────────────────
# Using fixed UUIDs means foreign-key references in tests and fixtures are
# predictable. In a real platform these would come from an import manifest.

# Organizations
ORG_TECHCORP   = uuid.UUID("10000000-0000-0000-0000-000000000001")
ORG_KPMG       = uuid.UUID("10000000-0000-0000-0000-000000000002")
ORG_PARTNERCO  = uuid.UUID("10000000-0000-0000-0000-000000000003")

# Permissions — ERP (SAP)
P_ERP_INVOICE_CREATE   = uuid.UUID("20000000-0000-0000-0000-000000000001")
P_ERP_INVOICE_READ     = uuid.UUID("20000000-0000-0000-0000-000000000002")
P_ERP_PAYMENT_APPROVE  = uuid.UUID("20000000-0000-0000-0000-000000000003")
P_ERP_PAYMENT_INITIATE = uuid.UUID("20000000-0000-0000-0000-000000000004")
P_ERP_ADMIN_FULL       = uuid.UUID("20000000-0000-0000-0000-000000000005")
P_ERP_AUDIT_LOG_DELETE = uuid.UUID("20000000-0000-0000-0000-000000000006")
P_ERP_DATA_READ        = uuid.UUID("20000000-0000-0000-0000-000000000007")

# Permissions — HR (Workday)
P_HR_EMPLOYEE_ADMIN    = uuid.UUID("20000000-0000-0000-0000-000000000008")
P_HR_PAYROLL_PROCESS   = uuid.UUID("20000000-0000-0000-0000-000000000009")
P_HR_REPORT_READ       = uuid.UUID("20000000-0000-0000-0000-000000000010")

# Permissions — CRM (Salesforce)
P_CRM_DATA_READ        = uuid.UUID("20000000-0000-0000-0000-000000000011")
P_CRM_DATA_EXPORT      = uuid.UUID("20000000-0000-0000-0000-000000000012")
P_CRM_ADMIN_FULL       = uuid.UUID("20000000-0000-0000-0000-000000000013")

# Permissions — Portal
P_PORTAL_VENDOR_ACCESS = uuid.UUID("20000000-0000-0000-0000-000000000014")
P_PORTAL_ADMIN_FULL    = uuid.UUID("20000000-0000-0000-0000-000000000015")

# Roles
R_ERP_ADMIN            = uuid.UUID("30000000-0000-0000-0000-000000000001")
R_ERP_READONLY         = uuid.UUID("30000000-0000-0000-0000-000000000002")
R_ERP_AUDITOR          = uuid.UUID("30000000-0000-0000-0000-000000000003")
R_FINANCE_CREATOR      = uuid.UUID("30000000-0000-0000-0000-000000000004")
R_FINANCE_APPROVER     = uuid.UUID("30000000-0000-0000-0000-000000000005")
R_HR_ADMIN             = uuid.UUID("30000000-0000-0000-0000-000000000006")
R_PAYROLL_ADMIN        = uuid.UUID("30000000-0000-0000-0000-000000000007")
R_HR_READONLY          = uuid.UUID("30000000-0000-0000-0000-000000000008")
R_CRM_READONLY         = uuid.UUID("30000000-0000-0000-0000-000000000009")
R_CRM_DATAEXPORT       = uuid.UUID("30000000-0000-0000-0000-000000000010")
R_VENDOR_PORTAL        = uuid.UUID("30000000-0000-0000-0000-000000000011")
R_PORTAL_ADMIN         = uuid.UUID("30000000-0000-0000-0000-000000000012")

# SoD rules
SOD_FINANCE_CREATE_APPROVE  = uuid.UUID("40000000-0000-0000-0000-000000000001")
SOD_PAYMENT_INITIATE_APPROVE= uuid.UUID("40000000-0000-0000-0000-000000000002")
SOD_HR_ADMIN_PAYROLL        = uuid.UUID("40000000-0000-0000-0000-000000000003")
SOD_ERP_ADMIN_AUDITDELETE   = uuid.UUID("40000000-0000-0000-0000-000000000004")

# Users
U_ALICE   = uuid.UUID("50000000-0000-0000-0000-000000000001")  # vendor   — TechCorp — SOX violation
U_BOB     = uuid.UUID("50000000-0000-0000-0000-000000000002")  # vendor   — TechCorp — clean
U_SARAH   = uuid.UUID("50000000-0000-0000-0000-000000000003")  # auditor  — KPMG
U_MICHAEL = uuid.UUID("50000000-0000-0000-0000-000000000004")  # auditor  — KPMG
U_DAVID   = uuid.UUID("50000000-0000-0000-0000-000000000005")  # contractor — PartnerCo — HIPAA violation
U_LISA    = uuid.UUID("50000000-0000-0000-0000-000000000006")  # contractor — PartnerCo — clean
U_RAJ     = uuid.UUID("50000000-0000-0000-0000-000000000007")  # b2b_admin — PartnerCo
U_EMMA    = uuid.UUID("50000000-0000-0000-0000-000000000008")  # partner   — PartnerCo

NOW = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# DATA DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

def build_organizations() -> list[Organization]:
    return [
        Organization(
            id=ORG_TECHCORP,
            name="TechCorp Systems",
            type="vendor",
            domain="techcorp.io",
            country="US",
            risk_tier=RiskTier.high,
            baa_executed=False,    # No BAA — blocks PHI access in compliance engine
            pci_scoped=True,       # In PCI scope — sensitive payment data access
            gdpr_dpa=True,
        ),
        Organization(
            id=ORG_KPMG,
            name="KPMG External Audit",
            type="auditor",
            domain="kpmg.com",
            country="US",
            risk_tier=RiskTier.low,
            baa_executed=True,     # Auditors have executed BAA
            pci_scoped=False,
            gdpr_dpa=True,
        ),
        Organization(
            id=ORG_PARTNERCO,
            name="PartnerCo Solutions",
            type="partner",
            domain="partnerco.com",
            country="DE",          # EU-based — GDPR residency checks apply
            risk_tier=RiskTier.medium,
            baa_executed=False,
            pci_scoped=False,
            gdpr_dpa=False,        # Missing DPA — blocks EU-data-scope access requests
        ),
    ]


def build_permissions() -> list[Permission]:
    """
    Atomic permission units. Each represents a single action on a resource
    in a specific enterprise system. Permissions map to roles; roles map to users.
    SoD rules reference permission pairs — not role pairs — for cross-system detection.
    """
    return [
        # ── SAP ERP ───────────────────────────────────────────────────────
        Permission(id=P_ERP_INVOICE_CREATE,
                   name="erp.invoice.create", display_name="Create Invoice",
                   resource="invoice", action="create",
                   system_name="SAP_ERP", is_sensitive=True),

        Permission(id=P_ERP_INVOICE_READ,
                   name="erp.invoice.read", display_name="Read Invoice",
                   resource="invoice", action="read",
                   system_name="SAP_ERP", is_sensitive=False),

        Permission(id=P_ERP_PAYMENT_APPROVE,
                   name="erp.payment.approve", display_name="Approve Payment",
                   resource="payment", action="approve",
                   system_name="SAP_ERP", is_sensitive=True),

        Permission(id=P_ERP_PAYMENT_INITIATE,
                   name="erp.payment.initiate", display_name="Initiate Payment",
                   resource="payment", action="initiate",
                   system_name="SAP_ERP", is_sensitive=True),

        Permission(id=P_ERP_ADMIN_FULL,
                   name="erp.admin.full", display_name="ERP Full Admin",
                   resource="erp_system", action="admin",
                   system_name="SAP_ERP", is_sensitive=True),

        Permission(id=P_ERP_AUDIT_LOG_DELETE,
                   name="erp.audit_log.delete", display_name="Delete ERP Audit Log",
                   resource="audit_log", action="delete",
                   system_name="SAP_ERP", is_sensitive=True),
        # WHY is erp.audit_log.delete sensitive?
        # Deleting audit logs is how financial fraud is concealed. The SOX-CC7.2
        # control requires that audit logs be complete and tamper-evident. An ERP
        # Admin who can also delete audit logs could cover their own tracks.

        Permission(id=P_ERP_DATA_READ,
                   name="erp.data.read", display_name="ERP Data Read",
                   resource="erp_data", action="read",
                   system_name="SAP_ERP", is_sensitive=False),

        # ── Workday HR ────────────────────────────────────────────────────
        Permission(id=P_HR_EMPLOYEE_ADMIN,
                   name="hr.employee.admin", display_name="HR Employee Admin",
                   resource="employee_record", action="admin",
                   system_name="HR_WORKDAY", is_sensitive=True),

        Permission(id=P_HR_PAYROLL_PROCESS,
                   name="hr.payroll.process", display_name="Process Payroll",
                   resource="payroll", action="process",
                   system_name="HR_WORKDAY", is_sensitive=True),
        # WHY is HR Admin + Payroll a conflict?
        # A single user who can both manage employee records and process payroll
        # could create a ghost employee and pay them. Classic HIPAA / HR fraud vector.

        Permission(id=P_HR_REPORT_READ,
                   name="hr.report.read", display_name="HR Reports Read",
                   resource="hr_report", action="read",
                   system_name="HR_WORKDAY", is_sensitive=False),

        # ── Salesforce CRM ───────────────────────────────────────────────
        Permission(id=P_CRM_DATA_READ,
                   name="crm.data.read", display_name="CRM Data Read",
                   resource="crm_data", action="read",
                   system_name="SALESFORCE_CRM", is_sensitive=False),

        Permission(id=P_CRM_DATA_EXPORT,
                   name="crm.data.export", display_name="CRM Data Export",
                   resource="crm_data", action="export",
                   system_name="SALESFORCE_CRM", is_sensitive=True),

        Permission(id=P_CRM_ADMIN_FULL,
                   name="crm.admin.full", display_name="CRM Full Admin",
                   resource="crm_system", action="admin",
                   system_name="SALESFORCE_CRM", is_sensitive=True),

        # ── Vendor Portal ────────────────────────────────────────────────
        Permission(id=P_PORTAL_VENDOR_ACCESS,
                   name="portal.vendor.access", display_name="Vendor Portal Access",
                   resource="vendor_portal", action="access",
                   system_name="NEXUS_PORTAL", is_sensitive=False),

        Permission(id=P_PORTAL_ADMIN_FULL,
                   name="portal.admin.full", display_name="Portal Full Admin",
                   resource="portal_system", action="admin",
                   system_name="NEXUS_PORTAL", is_sensitive=True),
    ]


def build_roles() -> list[Role]:
    """
    12 roles spanning 4 systems. Role names match what you'd see in a real
    enterprise IGA catalog: system-prefixed, scope-specific, risk-tiered.
    """
    return [
        # ── SAP ERP ───────────────────────────────────────────────────────
        Role(id=R_ERP_ADMIN,
             name="ERP_Admin", display_name="SAP ERP Administrator",
             description="Full administrative access to SAP ERP including configuration and user management.",
             scope="system", system_name="SAP_ERP",
             risk_level=RiskTier.critical, is_sensitive=True, is_privileged=True),

        Role(id=R_ERP_READONLY,
             name="ERP_ReadOnly", display_name="SAP ERP Read Only",
             description="Read-only access to ERP data and invoice records. Suitable for vendor audits.",
             scope="system", system_name="SAP_ERP",
             risk_level=RiskTier.low, is_sensitive=False, is_privileged=False),

        Role(id=R_ERP_AUDITOR,
             name="ERP_Auditor", display_name="SAP ERP External Auditor",
             description="Read access scoped for external audit engagements. Read invoices, read data.",
             scope="system", system_name="SAP_ERP",
             risk_level=RiskTier.low, is_sensitive=False, is_privileged=False),

        # ── Finance (operates on SAP_ERP permissions) ────────────────────
        Role(id=R_FINANCE_CREATOR,
             name="Finance_Creator", display_name="Finance Document Creator",
             description="Create invoices and initiate payments in the ERP financial module.",
             scope="application", system_name="SAP_ERP",
             risk_level=RiskTier.high, is_sensitive=True, is_privileged=False),

        Role(id=R_FINANCE_APPROVER,
             name="Finance_Approver", display_name="Finance Payment Approver",
             description="Approve payments in the ERP financial module. Sensitive — SOX-controlled.",
             scope="application", system_name="SAP_ERP",
             risk_level=RiskTier.critical, is_sensitive=True, is_privileged=True),

        # ── Workday HR ────────────────────────────────────────────────────
        Role(id=R_HR_ADMIN,
             name="HR_Admin", display_name="Workday HR Administrator",
             description="Full HR administration including employee record management.",
             scope="system", system_name="HR_WORKDAY",
             risk_level=RiskTier.high, is_sensitive=True, is_privileged=True),

        Role(id=R_PAYROLL_ADMIN,
             name="Payroll_Admin", display_name="Payroll Processor",
             description="Process payroll runs in Workday. Cannot be held by same person as HR_Admin.",
             scope="application", system_name="HR_WORKDAY",
             risk_level=RiskTier.critical, is_sensitive=True, is_privileged=True),

        Role(id=R_HR_READONLY,
             name="HR_ReadOnly", display_name="HR Reports Read Only",
             description="Read HR reports. Suitable for external auditors reviewing workforce data.",
             scope="application", system_name="HR_WORKDAY",
             risk_level=RiskTier.low, is_sensitive=False, is_privileged=False),

        # ── Salesforce CRM ───────────────────────────────────────────────
        Role(id=R_CRM_READONLY,
             name="CRM_ReadOnly", display_name="CRM Data Read Only",
             description="Read CRM records. Standard partner integration access.",
             scope="application", system_name="SALESFORCE_CRM",
             risk_level=RiskTier.low, is_sensitive=False, is_privileged=False),

        Role(id=R_CRM_DATAEXPORT,
             name="CRM_DataExport", display_name="CRM Data Export",
             description="Export CRM data. Sensitive — enables bulk customer data extraction.",
             scope="application", system_name="SALESFORCE_CRM",
             risk_level=RiskTier.high, is_sensitive=True, is_privileged=False),

        # ── Vendor Portal ────────────────────────────────────────────────
        Role(id=R_VENDOR_PORTAL,
             name="Vendor_Portal_Access", display_name="Vendor Portal Access",
             description="Standard access to the NexusGuard vendor self-service portal.",
             scope="application", system_name="NEXUS_PORTAL",
             risk_level=RiskTier.low, is_sensitive=False, is_privileged=False),

        Role(id=R_PORTAL_ADMIN,
             name="Portal_Admin", display_name="Vendor Portal Administrator",
             description="Administer vendor portal settings and user invitations.",
             scope="application", system_name="NEXUS_PORTAL",
             risk_level=RiskTier.high, is_sensitive=True, is_privileged=True),
    ]


def build_role_permissions() -> list[RolePermission]:
    """
    Maps roles to their constituent permissions. A role is just a named
    collection of permissions; the SoD engine operates on the permission level.
    """
    ADMIN_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    now = NOW

    def rp(role_id, perm_id):
        return RolePermission(role_id=role_id, permission_id=perm_id,
                              granted_by=ADMIN_UUID, granted_at=now)
    return [
        # ERP_Admin: full admin + read + can delete audit logs (the dangerous one)
        rp(R_ERP_ADMIN,        P_ERP_ADMIN_FULL),
        rp(R_ERP_ADMIN,        P_ERP_DATA_READ),
        rp(R_ERP_ADMIN,        P_ERP_AUDIT_LOG_DELETE),

        # ERP_ReadOnly: read-only, safe for general vendor access
        rp(R_ERP_READONLY,     P_ERP_DATA_READ),
        rp(R_ERP_READONLY,     P_ERP_INVOICE_READ),

        # ERP_Auditor: same as ReadOnly — scoped for external audit engagements
        rp(R_ERP_AUDITOR,      P_ERP_DATA_READ),
        rp(R_ERP_AUDITOR,      P_ERP_INVOICE_READ),

        # Finance_Creator: create invoices + initiate payments
        rp(R_FINANCE_CREATOR,  P_ERP_INVOICE_CREATE),
        rp(R_FINANCE_CREATOR,  P_ERP_PAYMENT_INITIATE),

        # Finance_Approver: only approve payments (no create)
        # CANNOT be held by same person as Finance_Creator — SOX-CC6.1
        rp(R_FINANCE_APPROVER, P_ERP_PAYMENT_APPROVE),

        # HR_Admin: employee admin + HR reports
        rp(R_HR_ADMIN,         P_HR_EMPLOYEE_ADMIN),
        rp(R_HR_ADMIN,         P_HR_REPORT_READ),

        # Payroll_Admin: process payroll only
        # CANNOT be held by same person as HR_Admin — HIPAA
        rp(R_PAYROLL_ADMIN,    P_HR_PAYROLL_PROCESS),

        # HR_ReadOnly: reports only — safe for auditors
        rp(R_HR_READONLY,      P_HR_REPORT_READ),

        # CRM roles
        rp(R_CRM_READONLY,     P_CRM_DATA_READ),
        rp(R_CRM_DATAEXPORT,   P_CRM_DATA_READ),
        rp(R_CRM_DATAEXPORT,   P_CRM_DATA_EXPORT),

        # Portal roles
        rp(R_VENDOR_PORTAL,    P_PORTAL_VENDOR_ACCESS),
        rp(R_PORTAL_ADMIN,     P_PORTAL_ADMIN_FULL),
        rp(R_PORTAL_ADMIN,     P_PORTAL_VENDOR_ACCESS),
    ]


def build_sod_rules() -> list[SoDRule]:
    """
    4 realistic SoD rules. Each maps to a published compliance control.
    All use permission-level references so cross-system detection works.

    In a real platform these rules come from the GRC team / compliance library.
    The compliance_control field is the exact control reference auditors cite.
    """
    ADMIN_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    return [
        SoDRule(
            id=SOD_FINANCE_CREATE_APPROVE,
            name="Finance Creator + Finance Approver",
            description=(
                "A single identity cannot both create invoices/initiate payments AND "
                "approve payments. This is the foundational financial SoD control. "
                "Violation enables fraudulent self-approved payments."
            ),
            permission_a_id=P_ERP_INVOICE_CREATE,
            permission_b_id=P_ERP_PAYMENT_APPROVE,
            severity=SoDSeverity.critical,
            compliance_control="SOX-CC6.1",
            is_active=True,
            created_by=ADMIN_UUID,
        ),
        SoDRule(
            id=SOD_PAYMENT_INITIATE_APPROVE,
            name="Payment Initiator + Payment Approver",
            description=(
                "A single identity cannot both initiate AND approve the same payment. "
                "Standard four-eyes payment control. Violation is a direct fraud vector."
            ),
            permission_a_id=P_ERP_PAYMENT_INITIATE,
            permission_b_id=P_ERP_PAYMENT_APPROVE,
            severity=SoDSeverity.critical,
            compliance_control="SOX-CC6.1",
            is_active=True,
            created_by=ADMIN_UUID,
        ),
        SoDRule(
            id=SOD_HR_ADMIN_PAYROLL,
            name="HR Admin + Payroll Admin",
            description=(
                "A single identity cannot administer employee records AND process payroll. "
                "Enables ghost employee creation + fraudulent payment. "
                "HIPAA also requires separation because HR admins can access PHI-adjacent records."
            ),
            permission_a_id=P_HR_EMPLOYEE_ADMIN,
            permission_b_id=P_HR_PAYROLL_PROCESS,
            severity=SoDSeverity.high,
            compliance_control="HIPAA-164.308(a)(3)",
            is_active=True,
            created_by=ADMIN_UUID,
        ),
        SoDRule(
            id=SOD_ERP_ADMIN_AUDITDELETE,
            name="ERP Admin + ERP Audit Log Delete",
            description=(
                "An ERP administrator cannot also have the ability to delete audit logs. "
                "Audit logs must be tamper-evident. An admin who can delete their own "
                "activity trail violates the SOX requirement for complete audit evidence."
            ),
            permission_a_id=P_ERP_ADMIN_FULL,
            permission_b_id=P_ERP_AUDIT_LOG_DELETE,
            severity=SoDSeverity.high,
            compliance_control="SOX-CC7.2",
            is_active=True,
            created_by=ADMIN_UUID,
        ),
    ]


def build_users() -> list[User]:
    """
    8 users across all identity classes. Contract expiry dates are chosen to
    exercise different lifecycle states:
      - Alice: contract in 12 days  → should trigger T-30 warning already
      - Bob:   already expired      → orphan account scenario
      - Others: 90–365 days out
    """
    return [
        # ── TechCorp Systems (vendor, high risk) ─────────────────────────
        User(
            id=U_ALICE,
            email="alice.chen@techcorp.io",
            first_name="Alice", last_name="Chen",
            display_name="Alice Chen",
            identity_class=IdentityClass.vendor,
            organization_id=ORG_TECHCORP,
            status=IdentityStatus.active,
            risk_tier=RiskTier.high,
            current_risk_score=Decimal("72.50"),
            source_system="salesforce",
            contract_id="SFDC-TC-2024-001",
            contract_expires_at=NOW + timedelta(days=12),  # expiring soon → T-30 warning
            onboarded_at=NOW - timedelta(days=180),
            last_login=NOW - timedelta(hours=3),
        ),
        User(
            id=U_BOB,
            email="bob.harris@techcorp.io",
            first_name="Bob", last_name="Harris",
            display_name="Bob Harris",
            identity_class=IdentityClass.vendor,
            organization_id=ORG_TECHCORP,
            status=IdentityStatus.active,
            risk_tier=RiskTier.medium,
            current_risk_score=Decimal("45.00"),
            source_system="salesforce",
            contract_id="SFDC-TC-2024-002",
            contract_expires_at=NOW - timedelta(days=14),  # already EXPIRED → orphan scenario
            onboarded_at=NOW - timedelta(days=365),
            last_login=NOW - timedelta(days=20),
        ),

        # ── KPMG External Audit (auditor, low risk) ──────────────────────
        User(
            id=U_SARAH,
            email="sarah.jones@kpmg.com",
            first_name="Sarah", last_name="Jones",
            display_name="Sarah Jones",
            identity_class=IdentityClass.auditor,
            organization_id=ORG_KPMG,
            status=IdentityStatus.active,
            risk_tier=RiskTier.low,
            current_risk_score=Decimal("18.00"),
            source_system="servicenow",
            contract_id="SNW-KPMG-2025-Q4",
            contract_expires_at=NOW + timedelta(days=90),
            onboarded_at=NOW - timedelta(days=30),
            last_login=NOW - timedelta(hours=26),
        ),
        User(
            id=U_MICHAEL,
            email="michael.zhang@kpmg.com",
            first_name="Michael", last_name="Zhang",
            display_name="Michael Zhang",
            identity_class=IdentityClass.auditor,
            organization_id=ORG_KPMG,
            status=IdentityStatus.active,
            risk_tier=RiskTier.low,
            current_risk_score=Decimal("22.00"),
            source_system="servicenow",
            contract_id="SNW-KPMG-2025-Q4",
            contract_expires_at=NOW + timedelta(days=90),
            onboarded_at=NOW - timedelta(days=30),
            last_login=NOW - timedelta(days=2),
        ),

        # ── PartnerCo Solutions (partner/contractor, medium risk) ────────
        User(
            id=U_DAVID,
            email="david.kim@partnerco.com",
            first_name="David", last_name="Kim",
            display_name="David Kim",
            identity_class=IdentityClass.contractor,
            organization_id=ORG_PARTNERCO,
            status=IdentityStatus.active,
            risk_tier=RiskTier.medium,
            current_risk_score=Decimal("55.00"),
            source_system="manual",
            contract_id="MAN-PC-2025-HR-001",
            contract_expires_at=NOW + timedelta(days=180),
            onboarded_at=NOW - timedelta(days=60),
            last_login=NOW - timedelta(days=1),
        ),
        User(
            id=U_LISA,
            email="lisa.wang@partnerco.com",
            first_name="Lisa", last_name="Wang",
            display_name="Lisa Wang",
            identity_class=IdentityClass.contractor,
            organization_id=ORG_PARTNERCO,
            status=IdentityStatus.active,
            risk_tier=RiskTier.low,
            current_risk_score=Decimal("30.00"),
            source_system="manual",
            contract_id="MAN-PC-2025-HR-002",
            contract_expires_at=NOW + timedelta(days=180),
            onboarded_at=NOW - timedelta(days=60),
            last_login=NOW - timedelta(hours=8),
        ),
        User(
            id=U_RAJ,
            email="raj.patel@partnerco.com",
            first_name="Raj", last_name="Patel",
            display_name="Raj Patel",
            identity_class=IdentityClass.b2b_admin,
            organization_id=ORG_PARTNERCO,
            status=IdentityStatus.active,
            risk_tier=RiskTier.medium,
            current_risk_score=Decimal("48.00"),
            source_system="manual",
            contract_id="MAN-PC-2025-ADM-001",
            contract_expires_at=NOW + timedelta(days=365),
            onboarded_at=NOW - timedelta(days=90),
            last_login=NOW - timedelta(hours=1),
        ),
        User(
            id=U_EMMA,
            email="emma.brooks@partnerco.com",
            first_name="Emma", last_name="Brooks",
            display_name="Emma Brooks",
            identity_class=IdentityClass.partner,
            organization_id=ORG_PARTNERCO,
            status=IdentityStatus.active,
            risk_tier=RiskTier.low,
            current_risk_score=Decimal("25.00"),
            source_system="manual",
            contract_id="MAN-PC-2025-PTR-001",
            contract_expires_at=NOW + timedelta(days=270),
            onboarded_at=NOW - timedelta(days=45),
            last_login=NOW - timedelta(days=3),
        ),
    ]


def build_user_roles() -> list[UserRole]:
    """
    Role assignments. Two users deliberately receive conflicting roles so the
    SoD scanner (called after this) will detect and record violations.

    INTENTIONAL VIOLATIONS:
      Alice (U_ALICE): Finance_Creator + Finance_Approver → SOX-CC6.1 violation
      David (U_DAVID): HR_Admin + Payroll_Admin           → HIPAA violation

    These bypass the SoD pre-check because we're inserting directly. In the
    real platform the API would block these; here they're seeded as demo data
    so the dashboard shows non-trivial SoD state.
    """
    ADMIN_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    now = NOW

    def ur(user_id, role_id, justification, expires_days=None):
        return UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=ADMIN_UUID,
            business_justification=justification,
            status="active",
            assigned_at=now - timedelta(days=30),
            expires_at=now + timedelta(days=expires_days) if expires_days else None,
        )

    return [
        # Alice — vendor at TechCorp — SOX VIOLATION: Finance_Creator + Finance_Approver
        ur(U_ALICE, R_FINANCE_CREATOR,
           "TechCorp vendor requires invoice creation for ERP integration."),
        ur(U_ALICE, R_FINANCE_APPROVER,                                       # ← VIOLATES SOX-CC6.1
           "INTENTIONAL DEMO VIOLATION: Alice should not hold both Creator and Approver.",
           expires_days=30),
        ur(U_ALICE, R_VENDOR_PORTAL,
           "Standard vendor portal access for TechCorp integration team."),

        # Bob — vendor at TechCorp — expired contract, clean roles
        ur(U_BOB, R_ERP_READONLY,
           "TechCorp vendor needs ERP read access for integration testing."),
        ur(U_BOB, R_VENDOR_PORTAL,
           "Standard vendor portal access."),

        # Sarah — KPMG auditor — read-only across two systems (clean)
        ur(U_SARAH, R_ERP_AUDITOR,
           "KPMG Q4 audit engagement — ERP invoice and data read access required."),
        ur(U_SARAH, R_HR_READONLY,
           "KPMG Q4 audit engagement — HR reports required for workforce compliance review."),

        # Michael — KPMG auditor — CRM read access (clean)
        ur(U_MICHAEL, R_ERP_READONLY,
           "KPMG audit — supplementary ERP read access."),
        ur(U_MICHAEL, R_CRM_READONLY,
           "KPMG audit — CRM data read for revenue recognition testing."),

        # David — PartnerCo contractor — HIPAA VIOLATION: HR_Admin + Payroll_Admin
        ur(U_DAVID, R_HR_ADMIN,
           "PartnerCo contractor managing HR system configuration for client."),
        ur(U_DAVID, R_PAYROLL_ADMIN,                                          # ← VIOLATES HIPAA
           "INTENTIONAL DEMO VIOLATION: David should not hold both HR_Admin and Payroll_Admin."),

        # Lisa — PartnerCo contractor — payroll only (clean)
        ur(U_LISA, R_PAYROLL_ADMIN,
           "PartnerCo contractor assigned payroll processing responsibility."),

        # Raj — PartnerCo b2b_admin — portal admin + ERP read (clean)
        ur(U_RAJ, R_PORTAL_ADMIN,
           "PartnerCo admin manages vendor portal configuration on behalf of partner org."),
        ur(U_RAJ, R_ERP_READONLY,
           "Raj needs ERP read access to validate integration data."),

        # Emma — PartnerCo partner — CRM read + portal access (clean)
        ur(U_EMMA, R_CRM_READONLY,
           "Partner integration requires CRM data read for pipeline synchronisation."),
        ur(U_EMMA, R_VENDOR_PORTAL,
           "Standard partner portal access."),
    ]


def build_review_campaign(created_by: uuid.UUID) -> ReviewCampaign:
    return ReviewCampaign(
        id=uuid.UUID("60000000-0000-0000-0000-000000000001"),
        name="Q2 2026 External Identity Access Certification",
        description=(
            "Quarterly SOX/HIPAA access certification for all active external identities. "
            "All vendor, contractor, and partner role assignments must be certified or revoked."
        ),
        status="active",
        campaign_type="quarterly",
        scope={"identity_classes": ["vendor", "contractor", "partner", "b2b_admin", "auditor"]},
        created_by=created_by,
        start_date=NOW,
        due_date=NOW + timedelta(days=30),
        compliance_standard="SOX",
        total_items=0,   # updated after items are generated
    )


# ─────────────────────────────────────────────────────────────────────────────
# SEEDING LOGIC
# ─────────────────────────────────────────────────────────────────────────────

async def already_seeded(db: AsyncSession) -> bool:
    """Check if seed data is already present to make the script idempotent."""
    result = await db.execute(
        select(Organization).where(Organization.id == ORG_TECHCORP)
    )
    return result.scalar_one_or_none() is not None


async def seed(db: AsyncSession) -> None:
    print("\n🛡️  NexusGuard — Seeding realistic IAM scenario\n")

    if await already_seeded(db):
        print("⚡ Seed data already present — nothing to do.")
        print("   To re-seed: truncate the tables and re-run this script.")
        return

    # ── 1. Organizations ─────────────────────────────────────────────────────
    print("🏢 Creating organizations...")
    orgs = build_organizations()
    for org in orgs:
        db.add(org)
    await db.flush()
    print(f"   ✔  {len(orgs)} organizations")

    # ── 2. Permissions ───────────────────────────────────────────────────────
    print("🔑 Creating permissions...")
    perms = build_permissions()
    for p in perms:
        db.add(p)
    await db.flush()
    print(f"   ✔  {len(perms)} permissions across 4 systems")

    # ── 3. Roles ─────────────────────────────────────────────────────────────
    print("📋 Creating roles...")
    roles = build_roles()
    for r in roles:
        db.add(r)
    await db.flush()
    print(f"   ✔  {len(roles)} roles")

    # ── 4. Role → Permission mappings ────────────────────────────────────────
    print("🔗 Mapping permissions to roles...")
    rps = build_role_permissions()
    for rp in rps:
        db.add(rp)
    await db.flush()
    print(f"   ✔  {len(rps)} role-permission assignments")

    # ── 5. SoD rules ─────────────────────────────────────────────────────────
    print("⚖️  Creating SoD rules...")
    rules = build_sod_rules()
    for rule in rules:
        db.add(rule)
    await db.flush()
    for r in rules:
        print(f"   ✔  [{r.severity.value.upper()}] {r.name}  ({r.compliance_control})")

    # ── 6. Users ─────────────────────────────────────────────────────────────
    org_map = {o.id: o.name for o in orgs}
    print("\n👤 Creating users...")
    users = build_users()
    for u in users:
        u.organization_name = org_map[u.organization_id]  # denormalized for easy display in dashboard; not strictly needed
        db.add(u)
    await db.flush()
    for u in users:
        org_name = next(o.name for o in orgs if o.id == u.organization_id)
        exp_str = (
            f"expires {u.contract_expires_at.strftime('%Y-%m-%d')}"
            if u.contract_expires_at else "no expiry"
        )
        print(f"   ✔  {u.display_name:<22} ({u.identity_class.value:<12}) "
              f"@ {org_name:<26} [{exp_str}]")

    # ── 7. Role assignments (including intentional violations) ───────────────
    print("\n🎭 Assigning roles (includes 2 intentional SoD violations for demo)...")
    user_roles = build_user_roles()
    for ur in user_roles:
        db.add(ur)
    await db.flush()

    role_map = {r.id: r.name for r in roles}
    user_map = {u.id: u.display_name for u in users}
    for ur in user_roles:
        flag = ""
        if (ur.user_id == U_ALICE and ur.role_id == R_FINANCE_APPROVER):
            flag = "  ⚠️  SOX-CC6.1 VIOLATION"
        elif (ur.user_id == U_DAVID and ur.role_id == R_PAYROLL_ADMIN):
            flag = "  ⚠️  HIPAA VIOLATION"
        print(f"   ✔  {user_map.get(ur.user_id, '?'):<22} → {role_map.get(ur.role_id, '?')}{flag}")

    # ── 8. Commit before running SoD scan ───────────────────────────────────
    # SoD engine queries the DB; data must be committed first so that
    # scan_user_violations can see the role assignments we just inserted.
    await db.commit()
    print("\n🔍 Running SoD scans to detect seeded violations...")

    # NOTE: db.bind / session.get_bind() are synchronous Session methods and
    # raise MissingGreenlet (gkpj) inside an async function. Never call them
    # in async code. The session is already connected — no explicit check needed.
    sod_engine = SoDEngine(db)
    violation_count = 0
    for u in users:
        violations = await sod_engine.scan_user_violations(u.id)
        if violations:
            violation_count += len(violations)
            print(f"   ⚠️  {user_map[u.id]}: {len(violations)} violation(s) detected and recorded")
    await db.commit()
    print(f"   ✔  {violation_count} SoD violations recorded")

    # ── 9. Access review campaign ────────────────────────────────────────────
    print("\n📋 Creating access review campaign...")
    REVIEWER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
    campaign = build_review_campaign(created_by=REVIEWER_UUID)
    db.add(campaign)
    await db.flush()

    # Generate review items for every active UserRole
    items_created = 0
    result = await db.execute(
        select(UserRole).where(UserRole.status == "active")
    )
    active_assignments = result.scalars().all()

    for ur in active_assignments:
        item = ReviewItem(
            campaign_id=campaign.id,
            user_id=ur.user_id,
            role_id=ur.role_id,
            reviewer_id=REVIEWER_UUID,
            decision=ReviewDecision.pending,
            risk_score_at_review=next(
                (u.current_risk_score for u in users if u.id == ur.user_id),
                Decimal("50.0"),
            ),
        )
        db.add(item)
        items_created += 1

    campaign.total_items = items_created
    await db.commit()
    print(f"   ✔  Campaign '{campaign.name}' — {items_created} review items")

    # ── 10. Summary ──────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("✅ Seed complete\n")
    print(f"  Organizations : {len(orgs)}")
    print(f"  Permissions   : {len(perms)}  (across SAP_ERP, HR_WORKDAY, SALESFORCE_CRM, NEXUS_PORTAL)")
    print(f"  Roles         : {len(roles)}")
    print(f"  SoD rules     : {len(rules)}  (2 critical SOX, 1 high HIPAA, 1 high SOX-CC7.2)")
    print(f"  Users         : {len(users)}")
    print(f"  Role assigns  : {len(user_roles)}")
    print(f"  SoD violations: {violation_count}  (Alice → SOX, David → HIPAA)")
    print(f"  Review items  : {items_created}")
    print()
    print("  Notable scenarios:")
    print("  • Alice (TechCorp): Finance_Creator + Finance_Approver → SOX-CC6.1 open violation")
    print("  • David (PartnerCo): HR_Admin + Payroll_Admin          → HIPAA open violation")
    print("  • Bob (TechCorp): contract expired 14 days ago         → orphan account scenario")
    print("  • Alice: contract expires in 12 days                   → T-30 lifecycle warning")
    print("  • PartnerCo: gdpr_dpa=False                            → EU-data access blocked")
    print()
    print("  Dashboard: http://localhost:3000")
    print("  API docs:  http://localhost:8000/api/docs")


async def main() -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            await seed(db)
        except Exception as e:
            await db.rollback()
            print(f"\n❌ Seed failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
