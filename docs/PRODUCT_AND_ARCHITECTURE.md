# NexusGuard — Product Design & System Architecture

---

## PART 2: Product Design

### Product Name: **NexusGuard**
*Tagline: "Identity Governance for the World Beyond Your Firewall"*

### Problem Statement
Enterprise IAM tools govern employee identities. CIAM tools authenticate customer identities. Neither governs external identities (vendors, partners, contractors, B2B customers) with the rigor required for modern compliance, zero trust, and supply chain security. NexusGuard is the first purpose-built External Identity Governance platform — combining CIAM-grade authentication integration, IGA-grade access governance, and real-time behavioral risk scoring into a single unified system.

### Target Users
| Segment | Use Case | Compliance Driver |
|---|---|---|
| Healthcare Systems | BA/vendor access to PHI-adjacent systems | HIPAA, HITRUST |
| Financial Institutions | Third-party auditor, fintech partner, vendor access | SOX, PCI DSS, GLBA |
| SaaS Platforms | ISV partner, reseller, enterprise customer admin access | SOC 2, ISO 27001 |
| Government Contractors | Subcontractor and partner access management | CMMC, FedRAMP |
| Enterprises (Fortune 500) | Supply chain vendor, consultant, contractor governance | SOX, GDPR, CCPA |

### Key Differentiators vs. Market Leaders

**vs. Okta/Auth0:**
- Okta does AuthN. NexusGuard does AuthN + full IGA lifecycle + behavioral risk + compliance enforcement
- Okta has no concept of access certification campaigns for external identities
- NexusGuard integrates with Okta as an IdP; it governs what Okta authenticates

**vs. SailPoint:**
- SailPoint governs employees using HR as the authoritative source
- NexusGuard governs externals using contract systems (Salesforce, ServiceNow, procurement) as authoritative sources
- NexusGuard provides real-time risk scoring; SailPoint's risk is batch/daily

**vs. Microsoft Entra External ID:**
- Entra External ID is authentication + basic RBAC in the Microsoft ecosystem
- NexusGuard is IdP-agnostic, multi-cloud, and provides full IGA governance that Entra lacks
- NexusGuard's SoD engine works across systems; Entra's RBAC is scoped to its own resources

**vs. CyberArk Vendor PAM:**
- CyberArk secures privileged sessions for vendors — point-in-time, not lifecycle
- NexusGuard governs the full external identity lifecycle from onboarding to deprovisioning
- NexusGuard covers all external access, not just privileged; CyberArk leaves non-privileged vendor access ungoverned

---

## PART 3: System Architecture

### Architecture Philosophy
- **Zero Trust for External Identities**: Continuous validation, never persistent implicit trust
- **Event-Driven**: Kafka-backed async processing for risk scoring, lifecycle events, audit
- **API-First**: Every capability exposed as API; integrates into existing IAM stacks
- **Compliance-Native**: GDPR, SOX, HIPAA, PCI DSS controls built in, not bolted on

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           NEXUSGUARD PLATFORM                                    │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        ENTRY / INGESTION LAYER                           │   │
│  │                                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │  CIAM IdP    │  │  SCIM API    │  │  CSV/Manual  │  │  Contract   │ │   │
│  │  │  Connectors  │  │  Ingestion   │  │  Import      │  │  System API │ │   │
│  │  │(Okta,Entra,  │  │              │  │              │  │(Salesforce, │ │   │
│  │  │  Ping,Auth0) │  │              │  │              │  │ServiceNow)  │ │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │   │
│  │         └────────────────┴──────────────────┴─────────────────┘        │   │
│  │                                    │                                     │   │
│  │                          Identity Normalization                           │   │
│  │                          & Deduplication Engine                          │   │
│  └──────────────────────────────────────┬───────────────────────────────────┘   │
│                                          │                                        │
│  ┌──────────────────────────────────────▼───────────────────────────────────┐   │
│  │                        AUTHENTICATION INTEGRATION LAYER                   │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │   │
│  │  │  Federation Hub  │    │  MFA Orchestrator │    │  Session Validator│  │   │
│  │  │  SAML/OIDC/OAuth │    │  (Step-up Auth)   │    │  (Continuous)     │  │   │
│  │  └──────────────────┘    └──────────────────┘    └───────────────────┘  │   │
│  └──────────────────────────────────────┬───────────────────────────────────┘   │
│                                          │                                        │
│  ┌──────────────────────────────────────▼───────────────────────────────────┐   │
│  │                         CORE GOVERNANCE ENGINE                            │   │
│  │                                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │  Risk Scoring│  │  RBAC/ABAC   │  │  SoD Engine  │  │  UAR/Access │ │   │
│  │  │  Engine      │  │  Engine      │  │              │  │  Review Eng.│ │   │
│  │  │              │  │              │  │              │  │             │ │   │
│  │  │ • Behavioral │  │ • Role Mgmt  │  │ • Conflict   │  │ • Campaigns │ │   │
│  │  │ • Geo/Device │  │ • Policy Eng.│  │   Detection  │  │ • Certific. │ │   │
│  │  │ • Time-based │  │ • Entitlement│  │ • Remediat.  │  │ • Escalation│ │   │
│  │  │ • Contextual │  │   Mapping    │  │   Workflow   │  │ • Revocation│ │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │   │
│  └─────────┴─────────────────┴─────────────────┴─────────────────┴─────────┘   │
│                                          │                                        │
│  ┌──────────────────────────────────────▼───────────────────────────────────┐   │
│  │                      LIFECYCLE MANAGEMENT LAYER                           │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │   │
│  │  │  Onboarding      │    │  Mover/Modifier   │    │  Offboarding      │  │   │
│  │  │  Workflow        │    │  Engine           │    │  & Deprovisioning │  │   │
│  │  │  (Compliance     │    │  (SCIM PUSH)      │    │  (Auto-trigger)   │  │   │
│  │  │   policy check)  │    │                   │    │                   │  │   │
│  │  └──────────────────┘    └──────────────────┘    └───────────────────┘  │   │
│  └──────────────────────────────────────┬───────────────────────────────────┘   │
│                                          │                                        │
│  ┌──────────────────────────────────────▼───────────────────────────────────┐   │
│  │                      AUDIT & COMPLIANCE LAYER                             │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │   │
│  │  │  Tamper-Evident  │    │  Compliance       │    │  Report Generator │  │   │
│  │  │  Audit Log       │    │  Policy Engine    │    │  (SOX/HIPAA/GDPR) │  │   │
│  │  │  (Hash-chained)  │    │  (SOX,HIPAA,PCI)  │    │                   │  │   │
│  │  └──────────────────┘    └──────────────────┘    └───────────────────┘  │   │
│  └──────────────────────────────────────┬───────────────────────────────────┘   │
│                                          │                                        │
│  ┌──────────────────────────────────────▼───────────────────────────────────┐   │
│  │                          STORAGE LAYER                                    │   │
│  │                                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │  PostgreSQL  │  │  Redis Cache │  │  Kafka Event │  │  S3/Blob    │ │   │
│  │  │  (Primary)   │  │  (Sessions,  │  │  Stream      │  │  (Audit     │ │   │
│  │  │              │  │   Risk Cache)│  │  (Events)    │  │   Archive)  │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     API GATEWAY / PRESENTATION LAYER                      │   │
│  │  REST API (FastAPI) │ GraphQL (Future) │ Webhooks │ React Dashboard       │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Microservices Breakdown

| Service | Responsibility | Tech Stack | Port |
|---|---|---|---|
| identity-ingestion-svc | SCIM, CSV, IdP connector normalization | Python/FastAPI | 8001 |
| auth-integration-svc | SAML/OIDC federation, session validation | Python/FastAPI | 8002 |
| risk-engine-svc | Behavioral scoring, real-time risk assessment | Python/FastAPI | 8003 |
| rbac-engine-svc | Role/permission management, ABAC policies | Python/FastAPI | 8004 |
| sod-engine-svc | SoD rule evaluation, conflict detection | Python/FastAPI | 8005 |
| uar-engine-svc | Access review campaigns, certification workflows | Python/FastAPI | 8006 |
| lifecycle-svc | Onboarding, mover, offboarding automation | Python/FastAPI | 8007 |
| audit-svc | Tamper-evident logging, compliance reporting | Python/FastAPI | 8008 |
| api-gateway | Auth, routing, rate limiting | FastAPI/Nginx | 8000 |
| frontend | React dashboard | React/Nginx | 3000 |

### Data Flow

**External Identity Onboarding Flow:**
1. Contract system webhook → identity-ingestion-svc receives payload
2. Identity normalized, deduplicated, stored in PostgreSQL (users table)
3. Compliance policy engine checks: BAA existence, data residency, risk tier
4. If compliant → SCIM provisioning to target systems via lifecycle-svc
5. RBAC engine assigns role based on identity class and contract scope
6. SoD engine validates new role assignment against existing entitlements
7. If SoD conflict → access request blocked, routed to approver
8. Audit event emitted → audit-svc stores hash-chained log entry
9. Risk engine creates baseline profile for new external identity

**Access Review Campaign Flow:**
1. UAR engine triggers campaign (schedule or event-based)
2. Campaign created, reviewers notified (email/webhook)
3. Reviewers certify/revoke access via dashboard
4. Revocations queued → lifecycle-svc executes SCIM deprovisioning
5. Deprovisioning events → audit-svc records with timestamp + reviewer
6. Campaign completion report generated → compliance export

**Risk Score Update Flow:**
1. AuthN event received (login, API call, failed auth)
2. risk-engine-svc processes: geo, device, time, frequency, data accessed
3. Risk score calculated (0-100), stored + cached in Redis
4. If risk > threshold → step-up auth triggered or session terminated
5. High-risk events → immediate audit log entry + alert webhook
