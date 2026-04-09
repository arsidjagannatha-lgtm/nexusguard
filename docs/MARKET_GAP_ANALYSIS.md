# NexusGuard — Market Gap Analysis
## IAM / CIAM / IGA for External Identities (2025)

---

## PART 1: Critical Market Gaps

### Gap 1: No Unified External Identity Governance (IGA) for Non-Employees
**Why it exists:**
SailPoint, Saviynt, and Omada were architected around employee (workforce) identities backed by HR systems (Workday, SAP). External identities — customers, partners, vendors, contractors — have no HR golden record, no lifecycle trigger, no authoritative onboarding source. CIAM tools (Okta/Auth0, Entra External ID) handle authentication but have zero governance: no role lifecycle, no access certification, no SoD analysis.

**Which tools fail:**
- SailPoint IIQ / IdentityNow: No native CIAM connector; external identity onboarding is manual or custom-built
- Saviynt: Partner/vendor governance bolted on; no real-time risk correlation
- Okta/Auth0: Pure AuthN/AuthZ — zero governance lifecycle
- Microsoft Entra External ID: Authentication + basic RBAC, no UAR campaigns, no SoD
- Ping Identity: Strong federation, weak IGA for externals
- ForgeRock: Workflow-heavy; external identity access reviews require heavy customization

**Real-world risk:**
- SOC 2 Type II failures: auditors flag "no evidence of periodic access review for third-party users"
- Vendor accounts persist for 18+ months after contract end (phantom access)
- Healthcare: HIPAA Business Associate accounts accessing PHI indefinitely after BA relationship ends
- Finance: SOX control failures when external auditors/contractors retain system access post-engagement

**Who benefits:** SaaS platforms with B2B portals, healthcare systems with BA networks, financial institutions with vendor ecosystems, government contractors managing partner access.

---

### Gap 2: Static Risk Scoring — No Behavioral UEBA for External Identities
**Why it exists:**
Enterprise UEBA tools (Splunk UBA, Microsoft Sentinel, Exabeam) are built for internal network behavior. They lack context for external identity patterns: API access from multiple geographic regions is normal for a global partner but suspicious for a single-location vendor. Risk thresholds are static (IP allowlists, MFA enrollment) — not behavioral baselines per-identity-class.

**Which tools fail:**
- Okta ThreatInsight: IP reputation only; no per-external-identity behavioral baseline
- CyberArk: PAM-focused; no CIAM behavioral risk engine
- Entra ID Protection: Workforce-only ML models trained on employee behavior patterns
- SailPoint: No real-time risk engine; risk scores are batch-calculated daily

**Real-world risk:**
- Supply chain attacks: Compromised vendor credentials used during off-hours API calls — never flagged
- Session hijacking of partner portals goes undetected for weeks
- GDPR Article 32: Insufficient technical measures to detect unauthorized access to personal data processing systems
- PCI DSS Requirement 10.6: No continuous risk monitoring for third-party access to cardholder data environments

**Who benefits:** Fintech platforms with open banking APIs, healthcare interoperability networks, SaaS marketplaces with ISV ecosystems.

---

### Gap 3: No SoD Engine for Cross-System External Identities
**Why it exists:**
SoD engines in SailPoint/Saviynt analyze conflicts within a single organization's role catalog. External identities often span multiple tenants and systems — a vendor user might be an Admin in the vendor portal, a Read-Write user in the customer's ERP integration, and a Billing approver in the payment system. No tool cross-correlates these multi-tenant, multi-system permissions to detect SoD conflicts for externals.

**Which tools fail:**
- SailPoint: SoD ruleset is org-scoped; cross-tenant conflicts invisible
- Saviynt: Same limitation — SOD policies don't traverse organizational boundaries
- Okta: No SoD concept at all
- ServiceNow IRM: Governance, not identity-native; manual rule creation

**Real-world risk:**
- Finance: A consultant has both "create invoice" and "approve payment" across two connected financial systems — classic SoD violation, never detected
- SOX IT General Controls failure: Auditors find conflicting access combinations not caught by periodic reviews
- Fraud vector: Malicious insider at a vendor company gains conflicting privileges enabling financial fraud

**Who benefits:** Enterprises with complex B2B integration ecosystems (ERP, SCM, financial platforms), any organization under SOX, ISO 27001, or PCI DSS with third-party access.

---

### Gap 4: No Automated External Identity Lifecycle — Orphan Account Epidemic
**Why it exists:**
Internal ILC (Identity Lifecycle) is triggered by HR events (hire, transfer, terminate). External identities have no equivalent trigger system. Vendor contracts live in Salesforce or procurement systems; partner agreements in SharePoint; contractor engagements in ServiceNow. No IAM tool natively integrates with these authoritative sources to automate external identity termination.

**Which tools fail:**
- All IGA tools: Rely on HR as joiner/mover/leaver trigger — external identity equivalents not built in
- Okta Lifecycle Management: Supports SCIM provisioning but no contract/engagement expiry awareness
- Entra External ID: Guest lifecycle is manual or requires custom Azure Logic Apps
- ForgeRock: Workflow-driven; no native procurement system connectors

**Real-world risk:**
- Average orphan vendor account lifespan: 14 months (Verizon DBIR 2024)
- Colonial Pipeline attack vector: Compromised VPN credentials of a former vendor
- GDPR Article 17 (Right to Erasure): Former customer identities retained in access systems indefinitely
- Internal audit finding: "X% of third-party accounts lack documented access justification"

**Who benefits:** Any enterprise with vendor/partner ecosystems, MSPs managing client environments, regulated industries under GDPR/CCPA/HIPAA.

---

### Gap 5: Federated Identity Trust Without Continuous Validation
**Why it exists:**
SAML/OIDC federation is "trust at login time" — once a partner IdP asserts identity, the relying party trusts it for the session duration. There is no continuous validation that the federated identity's privileges at the home IdP haven't changed (user terminated at partner org but session token still valid). Token lifetimes of 8-24 hours create windows of unauthorized access.

**Which tools fail:**
- All CIAM tools: Federation is point-in-time; continuous session health checks not implemented
- Ping Identity: Strong federation broker but no continuous federated session validation
- Okta: Token introspection available but not used for continuous federated identity validation
- ForgeRock: Continuous authentication exists for workforce; not architected for external federated identities

**Real-world risk:**
- Terminated partner employee retains active session for hours/days
- M&A scenarios: Acquired company's identities continue accessing acquirer's systems post-close
- NIST SP 800-63B continuous authentication requirements not met for high-assurance external access
- Zero Trust architecture gap: "Never trust, always verify" violated for federated external sessions

**Who benefits:** Enterprises with large partner ecosystems (healthcare networks, financial consortiums, government contractor networks).

---

### Gap 6: No Compliance-Aware Access Request for External Identities
**Why it exists:**
Internal access request systems (ServiceNow, SailPoint Access Request) have policy engines that know organizational policy context (department, location, clearance level). External identity access requests arrive from outside the organizational policy boundary — no tool can automatically apply compliance-aware policies (GDPR data residency, HIPAA BAA existence check, PCI DSS scope restriction) at the access request layer for external identities.

**Which tools fail:**
- SailPoint Access Request: Policy engine requires internal identity attributes; external identities lack these
- Saviynt: Access request for externals requires manual policy application
- ServiceNow IRM: Governance layer, not identity-native
- CyberArk Vendor PAM: Privileged access only; no compliance policy engine at request time

**Real-world risk:**
- Healthcare: Vendor granted access to PHI-containing systems before BAA is executed
- Finance: Third-party auditor accesses EU customer data from US location (GDPR Chapter V violation)
- PCI DSS: Vendor given access to cardholder data environment without documented business justification

**Who benefits:** Healthcare systems, financial institutions, global enterprises with data residency requirements.

---

### Gap 7: Audit Trails Are Fragmented Across Authentication and Authorization Systems
**Why it exists:**
AuthN events live in the IdP (Okta system logs, Entra sign-in logs). AuthZ decisions live in the application or API gateway. Identity governance events live in the IGA tool. Privileged access logs live in PAM (CyberArk). For external identities, these systems are rarely connected, making end-to-end audit trail reconstruction impossible without significant manual correlation. No single tool provides a tamper-evident, unified audit trail for external identity lifecycle + access + behavior.

**Which tools fail:**
- Every tool: Audit logs are system-scoped, not identity-journey-scoped
- SailPoint: IGA events only; no real-time access logs
- Okta: AuthN logs; no AuthZ context or governance correlation
- CyberArk: PAM session recording; disconnected from identity governance
- SIEM tools (Splunk): Aggregate logs but don't understand identity governance context

**Real-world risk:**
- SOC 2 Type II: "Unable to provide complete audit trail for third-party user X" — audit failure
- GDPR Article 30 (Records of Processing): Cannot demonstrate lawful basis and access control for external identities
- Forensic investigation: Breach timeline reconstruction takes weeks due to fragmented logs
- SOX ITGC: Auditors require unified evidence; manual correlation creates control deficiency findings

**Who benefits:** Any organization under compliance audit, security operations teams, forensic investigators, GRC professionals.

---

## Competitive Positioning Matrix

| Capability | Okta/Auth0 | Entra Ext ID | SailPoint | Saviynt | Ping | ForgeRock | **NexusGuard** |
|---|---|---|---|---|---|---|---|
| External IGA | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ⚠️ | ✅ |
| Behavioral Risk (External) | ⚠️ | ⚠️ | ❌ | ⚠️ | ❌ | ❌ | ✅ |
| Cross-System SoD | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ❌ | ✅ |
| Automated External Lifecycle | ⚠️ | ⚠️ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| Continuous Federated Validation | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ | ✅ |
| Compliance-Aware Access Request | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ❌ | ✅ |
| Unified Tamper-Evident Audit | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

Legend: ✅ Native | ⚠️ Partial/Custom | ❌ Not available
