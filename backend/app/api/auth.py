"""NexusGuard — Authentication API"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_password, decode_token

router = APIRouter()

# In production: query admin_users table. Demo uses hardcoded admins.
DEMO_USERS = {
    "admin@nexusguard.io": {
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFmE3J1MOqmFT.W",  # "admin123"
        "user_id": "00000000-0000-0000-0000-000000000001",
        "role": "admin",
        "is_admin": True,
    },
    "reviewer@nexusguard.io": {
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFmE3J1MOqmFT.W",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "role": "reviewer",
        "is_admin": False,
    },
}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    user_record = DEMO_USERS.get(data.email)
    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(data.password, user_record["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token_data = {
        "sub": user_record["user_id"],
        "email": data.email,
        "role": user_record["role"],
        "is_admin": user_record["is_admin"],
    }

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        user={
            "id": user_record["user_id"],
            "email": data.email,
            "role": user_record["role"],
            "is_admin": user_record["is_admin"],
        },
    )


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    token_data = {
        "sub": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
        "is_admin": payload.get("is_admin", False),
    }
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}
