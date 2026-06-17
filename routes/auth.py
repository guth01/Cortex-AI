"""
Authentication routes — register, login, current user, Google Sign-In.
"""

import os
from datetime import datetime
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from models import UserRegister, UserLogin, Token, UserResponse
from auth import get_password_hash, verify_password, create_access_token
from routes.deps import get_db, get_current_user

router = APIRouter()

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

class GoogleSignInRequest(BaseModel):
    credential: str  # Google access_token (from @react-oauth/google useGoogleLogin)
    email: str | None = None
    name: str | None = None



# ============================================================================
# AUTH ROUTES
# ============================================================================

@router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Register a new user.

    - Hashes password with bcrypt
    - Stores user in MongoDB Atlas
    - Returns JWT token
    """
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = get_password_hash(user_data.password)

    user_doc = {
        "email": user_data.email,
        "name": user_data.name,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow(),
    }

    await db.users.insert_one(user_doc)

    access_token = create_access_token(data={"sub": user_data.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Login with email and password.

    - Verifies credentials
    - Returns JWT token
    """
    user = await db.users.find_one({"email": credentials.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user's information.

    Protected route — requires valid JWT token.
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        created_at=current_user["created_at"],
        google_oauth_connected="google_access_token" in current_user,
    )


@router.post("/auth/google/login", response_model=Token)
async def google_sign_in(
    payload: GoogleSignInRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Authenticate via Google Sign-In (access_token from @react-oauth/google).
    Verifies the token by calling Google's userinfo endpoint,
    then finds or creates a local user account.
    Returns a JWT access token.
    """
    # Verify by fetching userinfo with the access_token
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {payload.credential}"},
            )
            resp.raise_for_status()
            userinfo = resp.json()
    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google access token",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not verify Google token",
        )

    email = userinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token missing email",
        )

    name = userinfo.get("name") or userinfo.get("given_name") or email.split("@")[0]

    # Find or create user
    user = await db.users.find_one({"email": email})
    if not user:
        user_doc = {
            "email": email,
            "name": name,
            "hashed_password": "",  # No password for Google-only accounts
            "created_at": datetime.utcnow(),
            "google_signin": True,
        }
        await db.users.insert_one(user_doc)
        print(f"[GOOGLE-SIGN-IN] Created new user: {email}")
    else:
        print(f"[GOOGLE-SIGN-IN] Existing user signed in: {email}")

    access_token = create_access_token(data={"sub": email})
    return {"access_token": access_token, "token_type": "bearer"}

