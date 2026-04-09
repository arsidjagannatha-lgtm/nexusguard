#!/usr/bin/env python3
"""
NexusGuard — Sample Data Seed Script
Run: python seed_data.py
Populates the database with realistic external identity scenarios.
"""
import asyncio
import httpx
import json
from datetime import datetime, timezone, timedelta
import random

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None


async def get_token(client: httpx.AsyncClient):
    global TOKEN
    res = await client.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@nexusguard.io",
        "password": "admin123"
    })
    TOKEN = res.json()["access_token"]
    return {"Authorization": f"Bearer {TOKEN}"}


VENDORS = [
    ("alice.chen@acmeconsulting.com",     "Alice",   "Chen",     "vendor",      "Acme Consulting"),
    ("bob.martinez@techpartner.io",       "Bob",     "Martinez", "partner",     "TechPartner Inc"),
    ("carol.smith@medsupply.com",         "Carol",   "Smith",    "vendor",      "MedSupply Co"),
    ("david.kim@auditfirm.com",           "David",   "Kim",      "auditor",     "AuditFirm LLP"),
    ("eve.johnson@softwaredev.io",        "Eve",     "Johnson",  "contractor",  "SoftwareDev LLC"),
    ("frank.liu@globallogistics.com",     "Frank",   "Liu",      "partner",     "Global Logistics"),
    ("grace.patel@financeops.com",        "Grace",   "Patel",    "vendor",      "FinanceOps Ltd"),
    ("henry.brown@securityauditor.com",   "Henry",   "Brown",    "auditor",     "SecurityAudit Co"),
    ("irene.davis@cloudservices.io",      "Irene",   "Davis",    "b2b_admin",   "CloudServices Inc"),
    ("james.wilson@enterprise.com",       "James",   "Wilson",   "customer",    "Enterprise Corp"),
    ("kate.moore@healthtech.com",         "Kate",    "Moore",    "partner",     "HealthTech Systems"),
    ("liam.taylor@paymentpro.io",         "Liam",    "Taylor",   "vendor",      "PaymentPro"),
    ("mia.anderson@consultgroup.com",     "Mia",     "Anderson", "contractor",  "ConsultGroup"),
    ("noah.thomas@datavault.com",         "Noah",    "Thomas",   "vendor",      "DataVault Inc"),
    ("olivia.jackson@apigateway.io",      "Olivia",  "Jackson",  "b2b_admin",   "APIGateway Corp"),
]

RISK_EVENTS = [
    {"event_type": "geo_anomaly",         "country": "RU", "is_new_device": True},
    {"event_type": "off_hours_access",    "country": "US", "is_new_device": False},
    {"event_type": "bulk_operation",      "country": "IN", "is_bulk_operation": True},
    {"event_type": "login_success",       "country": "US", "resource_sensitivity": "high"},
    {"event_type": "privilege_escalation","country": "DE", "privilege_escalation": True},
    {"event_type": "mfa_failure",         "country": "CN", "is_new_device": True},
]


async def seed(client: httpx.AsyncClient, headers: dict):
    created_users = []

    print("📥 Creating external identities...")
    for email, fn, ln, cls, org in VENDORS:
        expiry = (datetime.now(timezone.utc) + timedelta(days=random.choice([15, 60, 180, 365]))).isoformat()
        res = await client.post(f"{BASE_URL}/users/", headers=headers, json={
            "email": email,
            "first_name": fn,
            "last_name": ln,
            "identity_class": cls,
            "organization": org,
            "source_system": random.choice(["salesforce", "servicenow", "manual"]),
            "contract_expires_at": expiry,
        })
        if res.status_code == 201:
            user = res.json()
            created_users.append(user)
            print(f"  ✅ {fn} {ln} ({cls}) @ {org}")
        else:
            print(f"  ⚠️  {email}: {res.status_code} {res.text[:80]}")

    print(f"\n⚡ Simulating risk events for {len(created_users)} users...")
    for user in created_users:
        event = random.choice(RISK_EVENTS)
        await client.post(f"{BASE_URL}/risk/score", headers=headers, json={
            "user_id": user["id"],
            **event
        })

    print("\n🔍 Running SoD scans...")
    for user in created_users[:5]:
        res = await client.post(f"{BASE_URL}/sod/scan/{user['id']}", headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data["violations_found"] > 0:
                print(f"  ⚠️  SoD violations for {user['id'][:8]}: {data['violations_found']}")

    print("\n📋 Creating access review campaign...")
    start = datetime.now(timezone.utc).isoformat()
    due   = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    res = await client.post(f"{BASE_URL}/reviews/campaigns", headers=headers, json={
        "name": "Q1 2026 Vendor Access Certification",
        "campaign_type": "quarterly",
        "compliance_standard": "SOX",
        "start_date": start,
        "due_date": due,
        "description": "Quarterly SOX access certification for all external vendor identities",
    })
    if res.status_code == 201:
        c = res.json()
        print(f"  ✅ Campaign created: {c['campaign_id']} ({c['total_items']} items)")
    else:
        print(f"  ⚠️  Campaign: {res.status_code}")

    print("\n📊 Seed complete! Summary:")
    print(f"  • Users created:   {len(created_users)}")
    print(f"  • Risk events:     {len(created_users)}")
    print(f"  • Visit: http://localhost:3000")
    print(f"  • API:   http://localhost:8000/api/docs")


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            headers = await get_token(client)
            await seed(client, headers)
        except httpx.ConnectError:
            print("❌ Cannot connect to API. Is the backend running?")
            print("   Run: docker-compose up -d  or  uvicorn app.main:app --reload")


if __name__ == "__main__":
    asyncio.run(main())
