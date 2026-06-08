"""
Google OAuth 2.0 routes for Calendar integration.

GET  /auth/google           → redirect to Google consent screen
GET  /auth/google/callback  → exchange code, store tokens, redirect to frontend
"""

import os
from datetime import datetime
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from routes.deps import get_db, get_current_user

router = APIRouter(prefix="/auth", tags=["google-oauth"])

# ============================================================================
# OAuth configuration
# ============================================================================

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = " ".join([
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
])

FRONTEND_DASHBOARD = os.getenv("FRONTEND_URL", "http://localhost:3000") + "/dashboard"


def _get_oauth_config() -> dict:
    """Read OAuth credentials from environment at call time (not import time)."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


# ============================================================================
# POST /auth/google/url  — get OAuth URL for frontend
# GET /auth/google  — initiate OAuth flow (legacy/direct redirect)
# ============================================================================

@router.post("/google/url")
async def get_google_oauth_url(
    current_user: dict = Depends(get_current_user),
):
    """Return the Google OAuth consent URL for the frontend to redirect to."""
    cfg = _get_oauth_config()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": current_user["id"],
    }
    consent_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"url": consent_url}


@router.get("/google")
async def google_oauth_initiate(
    current_user: dict = Depends(get_current_user),
):
    """
    Redirect authenticated user to Google's OAuth 2.0 consent screen.

    Requires the user to already be logged in (JWT Bearer token) so we can
    associate the Google tokens with the correct Atlas user document.

    Scopes requested:
      - openid
      - email
      - calendar.events  (create / edit events)
      - calendar.readonly (read events)
    """
    cfg = _get_oauth_config()

    # Encode the user's internal ID in the state param so the callback knows
    # which Atlas user to update (simple approach — no CSRF protection needed
    # for a dev/internal tool; add a signed state param for production).
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",       # ensures we get a refresh_token
        "prompt": "consent",            # force consent screen to always get refresh_token
        "state": current_user["id"],    # we'll read this back in the callback
    }

    consent_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    print(f"[OAUTH] Redirecting user {current_user['id']} to Google consent screen")
    return RedirectResponse(url=consent_url)


# ============================================================================
# GET /auth/google/callback  — exchange code for tokens
# ============================================================================

@router.get("/google/callback")
async def google_oauth_callback(
    code: str,
    state: str,  # user_id encoded in state param
    db: AsyncIOMotorDatabase = Depends(get_db),
    error: str = None,
):
    """
    Handle Google's OAuth 2.0 redirect callback.

    Steps:
    1. Check for OAuth error (user denied consent)
    2. Exchange authorization code for access + refresh tokens
    3. Store tokens in Atlas users collection
    4. Redirect to frontend dashboard with oauth=success query param
    """
    # Step 1: Handle consent denial
    if error:
        print(f"[OAUTH] User denied consent: {error}")
        return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=denied")

    cfg = _get_oauth_config()
    user_id = state  # we put user_id in state during initiation

    # Step 2: Exchange code for tokens
    print(f"[OAUTH] Exchanging code for tokens (user={user_id})...")
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": cfg["redirect_uri"],
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            token_response.raise_for_status()
            token_data = token_response.json()

    except httpx.HTTPStatusError as e:
        print(f"[OAUTH] Token exchange failed: {e.response.text}")
        return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=error&reason=token_exchange")
    except Exception as e:
        print(f"[OAUTH] Unexpected error during token exchange: {e}")
        return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=error&reason=unknown")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)  # seconds

    if not access_token:
        print(f"[OAUTH] No access_token in response: {token_data}")
        return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=error&reason=no_token")

    # Calculate expiry datetime (UTC)
    from datetime import timedelta
    token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

    # Step 3: Fetch Google user info (for logging / verification)
    try:
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            userinfo = userinfo_response.json()
            google_email = userinfo.get("email", "unknown")
    except Exception:
        google_email = "unknown"

    print(f"[OAUTH] Tokens received for Google account: {google_email}")

    # Step 4: Store tokens in Atlas
    try:
        update_doc = {
            "google_access_token": access_token,
            "google_token_expiry": token_expiry,
            "google_email": google_email,
            "google_oauth_connected_at": datetime.utcnow(),
        }
        # Only update refresh_token if we received one
        # (Google only sends it on first consent or when prompt=consent)
        if refresh_token:
            update_doc["google_refresh_token"] = refresh_token

        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_doc},
        )

        if result.matched_count == 0:
            print(f"[OAUTH] Warning: user {user_id} not found in Atlas")
            return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=error&reason=user_not_found")

        print(f"[OAUTH] Tokens stored for user {user_id} (Google: {google_email})")

    except Exception as e:
        print(f"[OAUTH] Failed to store tokens: {e}")
        return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=error&reason=db_write")

    # Step 5: Redirect to frontend dashboard
    return RedirectResponse(url=f"{FRONTEND_DASHBOARD}?oauth=success&google_email={google_email}")
