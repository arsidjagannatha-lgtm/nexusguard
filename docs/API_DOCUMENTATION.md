# NexusGuard API Documentation
## Base URL: `http://localhost:8000/api/v1`

---

## Authentication

All endpoints (except `/auth/login`) require Bearer token.

### POST `/auth/login`
```json
{ "email": "admin@nexusguard.io", "password": "admin123" }
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "...", "email": "...", "role": "admin", "is_admin": true }
}
```

---

## Users (External Identities)

### POST `/users/`
Onboard a new external identity.
```json
{
  "email": "vendor@partner.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "identity_class": "vendor",         // vendor|partner|contractor|customer|b2b_admin|auditor
  "organization": "Acme Corp",
  "source_system": "salesforce",      // optional
  "contract_id": "CONTRACT-2026-001", // optional
  "contract_expires_at": "2026-12-31T00:00:00Z" // optional
}
```

### GET `/users/?status=active&risk_tier=high&search=acme&limit=50`
List external identities with filtering.

### GET `/users/{user_id}`
Get user by ID.

### GET `/users/{user_id}/summary`
Full identity summary: user + active roles + risk score + SoD violations.

### PATCH `/users/{user_id}/status`
```json
{ "status": "suspended", "reason": "Contract under review" }
```

### DELETE `/users/{user_id}/deprovision?reason=Contract+expired`
Immediately deprovision — revokes all active roles and logs to audit trail.

---

## Risk Engine

### POST `/risk/score`
Calculate and update risk score based on an event.
```json
{
  "user_id": "uuid",
  "event_type": "geo_anomaly",        // geo_anomaly|off_hours_access|bulk_operation|etc.
  "country": "RU",                    // optional
  "device_id": "device-fingerprint",  // optional
  "is_new_device": true,              // optional
  "is_bulk_operation": false,         // optional
  "privilege_escalation": false,      // optional
  "resource_sensitivity": "high"      // optional: low|medium|high|critical
}
```
**Response:**
```json
{
  "score": 82.5,
  "tier": "high",
  "factors": { "geo_anomaly": 25.0, "off_hours_access": 15.0 },
  "delta": 15.3,
  "requires_step_up_auth": true,
  "requires_session_termination": false
}
```

### GET `/risk/users/{user_id}/trend?days=30`
Risk score history for trend charts.

### GET `/risk/high-risk-users`
All active users with high or critical risk scores.

---

## Roles & Permissions

### GET `/roles/`
List all roles with risk metadata.

### POST `/roles/assign`
Assign a role — **automatically runs SoD check before assignment**.
```json
{
  "user_id": "uuid",
  "role_id": "uuid",
  "business_justification": "Vendor requires read access for integration support",
  "expires_at": "2026-06-30T00:00:00Z"  // optional
}
```
**Response (SoD blocked):**
```json
{
  "assigned": false,
  "blocked": true,
  "reason": "SoD violation detected — assignment blocked",
  "violations": [{ "rule_name": "Invoice Create + Payment Approve", "severity": "critical" }]
}
```

### GET `/roles/permissions`
List all permissions with sensitivity metadata.

---

## SoD Engine

### GET `/sod/violations?status=open`
List violations filtered by status (open|mitigated|accepted|remediated|false_positive).

### GET `/sod/violations/summary`
```json
{
  "total_open": 12,
  "by_severity": { "critical": 2, "high": 5, "medium": 3, "low": 2 },
  "requires_immediate_action": 7
}
```

### POST `/sod/scan/{user_id}`
Run a full SoD scan for a specific user — detects and records new violations.

### POST `/sod/violations/{violation_id}/remediate`
```json
{
  "action": "accept",              // accept|remediate|mitigate
  "reason": "Risk accepted with compensating control",
  "mitigating_control": "Monthly access review required"
}
```

### GET `/sod/rules`
List all active SoD rules with compliance control mapping.

---

## Access Reviews

### POST `/reviews/campaigns`
Create and launch a review campaign — auto-generates items for all active users.
```json
{
  "name": "Q1 2026 Vendor Access Review",
  "campaign_type": "quarterly",          // quarterly|annual|triggered|ad_hoc
  "compliance_standard": "SOX",          // SOX|HIPAA|PCI-DSS|ISO-27001|SOC2
  "start_date": "2026-01-01T00:00:00Z",
  "due_date": "2026-01-31T00:00:00Z"
}
```

### GET `/reviews/campaigns`
List all campaigns with completion rates and counts.

### GET `/reviews/campaigns/{campaign_id}/items?decision=pending`
Get review items filtered by decision.

### POST `/reviews/items/{item_id}/decide`
Submit a certification decision — revoked access is automatically deprovisioned.
```json
{
  "decision": "revoked",                 // certified|revoked|escalated
  "justification": "Vendor contract ended — access no longer required"
}
```

---

## Audit Log

### GET `/audit/events?category=sod_event&limit=100`
List audit events filtered by category.

Categories: `identity_lifecycle` | `access_change` | `authentication` | `authorization` | `risk_event` | `review_action` | `sod_event` | `admin_action`

### GET `/audit/integrity?limit=1000`
Verify SHA-256 hash chain integrity. Detects any tampering.
```json
{
  "total_events_checked": 847,
  "chain_valid": true,
  "broken_links": [],
  "integrity_status": "VALID",
  "checked_at": "2026-01-15T10:30:00Z"
}
```

---

## Dashboard

### GET `/dashboard/summary`
Full KPI summary: users, risk distribution, SoD counts, campaign status.

### GET `/dashboard/identity-breakdown`
Identity count by class (vendor, partner, contractor, etc.)

### GET `/dashboard/recent-activity`
Last 20 audit events for activity feed.

### GET `/dashboard/risk-heatmap`
Top 50 users by risk score for heatmap visualization.
