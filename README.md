# 🛡️ NexusGuard
### External Identity Governance Platform
*"Identity Governance for the World Beyond Your Firewall"*

---

## What is NexusGuard?

NexusGuard is a production-grade **External Identity Governance (xIGA)** platform — the missing layer between CIAM authentication tools (Okta, Entra, Ping) and enterprise IGA platforms (SailPoint, Saviynt) for governing **vendors, partners, contractors, and B2B customers**.

It solves 7 critical gaps in the $16B IAM market that no existing tool addresses natively.

---

## Quick Start

### Option 1 — Docker Compose (recommended)
```bash
git clone https://github.com/yourname/nexusguard
cd nexusguard

# Start all services (PostgreSQL, Redis, Backend API, Frontend)
docker-compose up -d

# Seed demo data
cd backend && pip install httpx && python seed_data.py

# Open dashboard
open http://localhost:3000
```

**Demo credentials:** `admin@nexusguard.io` / `admin123`

---

### Option 2 — Local Development

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your PostgreSQL connection string

# Initialize database (requires running PostgreSQL)
psql -U nexus -d nexusguard -f ../db/schema.sql

# Start API server
uvicorn app.main:app --reload --port 8000

# Seed sample data
python seed_data.py
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# → http://localhost:3000
```

#### Run Tests
```bash
cd backend
pytest tests/ -v
```

---

## Project Structure

```
nexusguard/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers
│   │   │   ├── auth.py        # JWT authentication
│   │   │   ├── users.py       # External identity CRUD + lifecycle
│   │   │   ├── roles.py       # RBAC + SoD-checked role assignment
│   │   │   ├── risk.py        # Risk scoring engine API
│   │   │   ├── sod.py         # SoD violation management
│   │   │   ├── reviews.py     # UAR campaign management
│   │   │   ├── audit.py       # Tamper-evident audit log
│   │   │   └── dashboard.py   # KPI aggregation
│   │   ├── core/
│   │   │   ├── config.py      # Settings (env-based)
│   │   │   ├── database.py    # Async SQLAlchemy setup
│   │   │   └── security.py    # JWT + password hashing
│   │   ├── models/
│   │   │   └── models.py      # SQLAlchemy ORM models (all 12 tables)
│   │   ├── services/
│   │   │   ├── risk_engine.py     # Behavioral risk scoring (UEBA-lite)
│   │   │   ├── sod_engine.py      # SoD conflict detection + remediation
│   │   │   └── audit_service.py   # Hash-chained tamper-evident logging
│   │   ├── middleware/
│   │   │   └── audit_middleware.py
│   │   └── main.py
│   ├── tests/
│   │   └── test_core.py       # Risk engine, hash chain, SoD, lifecycle tests
│   ├── seed_data.py           # Demo data population
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx   # Risk overview + KPIs + charts
│       │   ├── UsersPage.tsx       # Identity list + onboarding + deprovision
│       │   ├── ReviewsPage.tsx     # UAR campaign management + decisions
│       │   ├── SoDPage.tsx         # SoD violation triage + remediation
│       │   ├── AuditPage.tsx       # Hash-chain audit log + integrity check
│       │   └── LoginPage.tsx
│       ├── components/
│       │   └── Layout.tsx          # Sidebar navigation
│       ├── store/
│       │   └── authStore.ts        # Zustand auth state
│       └── utils/
│           └── api.ts              # Axios with JWT interceptor
│
├── db/
│   └── schema.sql             # Full PostgreSQL schema with sample data
│
├── docs/
│   ├── MARKET_GAP_ANALYSIS.md
│   ├── PRODUCT_AND_ARCHITECTURE.md
│   ├── API_DOCUMENTATION.md
│   └── POSITIONING_AND_INTERVIEW_GUIDE.md
│
├── docker-compose.yml
└── README.md
```

---

## Key Features

### 🔍 Real-Time Behavioral Risk Scoring
- Per-event risk calculation using exponential moving average
- 11 behavioral signals: geo anomaly, off-hours, new device, bulk operations, privilege escalation
- Risk tier classification: Critical / High / Medium / Low / Minimal
- Step-up auth and session termination triggers

### ⚖️ Cross-System SoD Detection
- Pre-assignment SoD check — blocks conflicting access before it's granted
- Configurable SoD ruleset with compliance control mapping (SOX-CC6.1, PCI-7.1)
- Full remediation workflow: accept, mitigate, or remediate
- Dashboard showing violations by severity

### 📋 Access Review Campaigns
- Auto-generates review items for all active users
- Reviewer queue with one-click certify/revoke
- Automated deprovisioning on revocation decision
- Real-time completion tracking for SLA compliance

### 🔒 Tamper-Evident Audit Log
- SHA-256 hash chain — each event references previous event hash
- Chain integrity verification API — detects any single-event tampering
- Category-based filtering: identity lifecycle, SoD events, review actions
- Audit evidence export for SOX/HIPAA/PCI auditors

### 🏗️ Identity Lifecycle Automation
- Contract-aware expiry detection (30-day warning)
- One-click deprovisioning with cascading role revocation
- Full audit trail from onboarding to offboarding
- Inactivity detection (90-day threshold configurable)

---

## API Reference

Full API documentation: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

Interactive docs (when running): http://localhost:8000/api/docs

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API | FastAPI + Python 3.12 | Async-native, type-safe, OpenAPI auto-docs |
| ORM | SQLAlchemy 2.0 (async) | Async throughout, no sync bottlenecks |
| Database | PostgreSQL 16 | Partitioned audit tables, JSONB for flexible payloads |
| Cache | Redis 7 | Risk score caching, session management |
| Auth | PyJWT + passlib/bcrypt | Industry-standard JWT with secure hashing |
| Frontend | React 18 + TypeScript | Type-safe UI with Vite for fast DX |
| State | Zustand | Lightweight, no boilerplate |
| Charts | Recharts | Composable, React-native charts |
| Styling | Tailwind CSS | Utility-first, zero runtime |
| Testing | pytest + pytest-asyncio | Async test support |
| Container | Docker + Docker Compose | One-command local environment |

---

## Compliance Coverage

| Standard | Controls Addressed |
|---|---|
| **SOX ITGC** | CC6.1 (Access Controls), CC6.2 (Authentication), CC6.3 (Authorization), CC7.2 (Monitoring) |
| **HIPAA** | §164.308(a)(3) (Workforce Security), §164.308(a)(1)(ii)(D) (Audit Controls) |
| **PCI DSS** | Req 7 (Access Control), Req 8 (Identity Management), Req 10 (Logging) |
| **SOC 2 Type II** | CC6.1-CC6.8 (Logical Access), CC7.1-CC7.2 (Monitoring) |
| **ISO 27001** | A.9 (Access Control), A.12.4 (Logging and Monitoring) |
| **GDPR** | Art. 25 (Privacy by Design), Art. 30 (Records of Processing), Art. 32 (Security Measures) |

---

## Market Context

NexusGuard addresses a documented gap in the IAM market:
- **Okta/Auth0**: Authentication only — no governance lifecycle
- **SailPoint/Saviynt**: Employee IGA — external identity governance is unsupported or heavily customized
- **Microsoft Entra External ID**: Authentication + basic RBAC — no UAR, no SoD, no behavioral risk
- **CyberArk**: Privileged access for vendors — doesn't govern non-privileged external access

See [docs/MARKET_GAP_ANALYSIS.md](docs/MARKET_GAP_ANALYSIS.md) for full competitive analysis.
See [docs/POSITIONING_AND_INTERVIEW_GUIDE.md](docs/POSITIONING_AND_INTERVIEW_GUIDE.md) for interview prep.

---

## License
MIT — Use freely for portfolio, demonstration, and production.
