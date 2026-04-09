"""NexusGuard — Core Configuration"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "nexusguard-dev-secret-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql+asyncpg://nexus:nexuspass@localhost:5432/nexusguard"
    REDIS_URL: str = "redis://localhost:6379/0"

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://nexusguard.local",
    ]

    # Risk scoring thresholds
    RISK_HIGH_THRESHOLD: float = 70.0
    RISK_CRITICAL_THRESHOLD: float = 85.0
    RISK_STEP_UP_AUTH_THRESHOLD: float = 75.0

    # Deprovisioning
    DEPROVISION_GRACE_PERIOD_HOURS: int = 24
    INACTIVITY_DEPROVISION_DAYS: int = 90

    class Config:
        env_file = ".env"


settings = Settings()
