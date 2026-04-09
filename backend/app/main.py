"""
NexusGuard — External Identity Governance Platform
FastAPI Backend — Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.api import users, roles, risk, reviews, sod, audit, auth, dashboard
from app.middleware.audit_middleware import AuditMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🛡️  NexusGuard IAM Platform starting — {settings.APP_ENV}")
    yield
    # Shutdown
    print("NexusGuard shutting down.")


app = FastAPI(
    title="NexusGuard IAM",
    description="External Identity Governance Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(users.router,     prefix="/api/v1/users",     tags=["Users"])
app.include_router(roles.router,     prefix="/api/v1/roles",     tags=["Roles & Permissions"])
app.include_router(risk.router,      prefix="/api/v1/risk",      tags=["Risk Engine"])
app.include_router(reviews.router,   prefix="/api/v1/reviews",   tags=["Access Reviews"])
app.include_router(sod.router,       prefix="/api/v1/sod",       tags=["SoD Engine"])
app.include_router(audit.router,     prefix="/api/v1/audit",     tags=["Audit"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "service": "nexusguard-api", "version": "1.0.0"}
