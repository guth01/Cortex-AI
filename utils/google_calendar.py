"""
Google Calendar utilities — token management and service construction.

get_valid_token(user_id, db)
    → checks Atlas for token_expiry, refreshes if expired, returns valid access_token

get_calendar_service(user_id, db)
    → builds a googleapiclient Calendar v3 service object ready to call
"""

import os
from datetime import datetime, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from motor.motor_asyncio import AsyncIOMotorDatabase


# ============================================================================
# Internal helpers
# ============================================================================

def _token_is_expired(token_expiry: Optional[datetime]) -> bool:
    """Return True if the token is missing or within 60 seconds of expiry."""
    if token_expiry is None:
        return True
    # Normalise to UTC-aware
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    # Refresh a minute early to avoid clock-skew issues
    return (token_expiry - now).total_seconds() < 60


def _build_credentials(user: dict) -> Credentials:
    """Build a google.oauth2.Credentials object from Atlas user doc fields."""
    return Credentials(
        token=user.get("google_access_token"),
        refresh_token=user.get("google_refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly",
        ],
    )


# ============================================================================
# Public API
# ============================================================================

async def get_valid_token(user_id: str, db: AsyncIOMotorDatabase) -> str:
    """
    Return a valid Google OAuth access token for the given user.

    If the stored token is expired (or within 60s of expiry), automatically
    refreshes it using the refresh_token and persists the new tokens to Atlas.

    Args:
        user_id: MongoDB ObjectId string of the user
        db:      AsyncIOMotorDatabase instance

    Returns:
        A valid access_token string

    Raises:
        ValueError: if user has no Google OAuth tokens linked
        RuntimeError: if token refresh fails
    """
    from bson import ObjectId

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise ValueError(f"User {user_id} not found")

    if not user.get("google_access_token"):
        raise ValueError(
            "User has not connected Google Calendar. "
            "Please complete OAuth at GET /auth/google"
        )

    token_expiry: Optional[datetime] = user.get("google_token_expiry")

    if not _token_is_expired(token_expiry):
        # Token is still valid
        print(f"[GCAL] Token valid for user {user_id}")
        return user["google_access_token"]

    # Token expired — refresh it
    print(f"[GCAL] Token expired for user {user_id}, refreshing...")

    creds = _build_credentials(user)
    try:
        creds.refresh(Request())
    except Exception as e:
        raise RuntimeError(f"Failed to refresh Google token: {e}") from e

    # Persist new tokens to Atlas
    new_expiry = creds.expiry  # datetime (UTC-naive from google-auth)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "google_access_token": creds.token,
                "google_token_expiry": new_expiry,
                # refresh_token rarely changes but update just in case
                "google_refresh_token": creds.refresh_token or user.get("google_refresh_token"),
            }
        },
    )

    print(f"[GCAL] Token refreshed for user {user_id}, expires={new_expiry}")
    return creds.token


async def get_calendar_service(user_id: str, db: AsyncIOMotorDatabase):
    """
    Build and return an authorized Google Calendar API v3 service object.

    Args:
        user_id: MongoDB ObjectId string of the user
        db:      AsyncIOMotorDatabase instance

    Returns:
        googleapiclient Resource object (calendar v3)
    """
    access_token = await get_valid_token(user_id, db)

    # Build minimal credentials with just the access_token
    # (google-api-python-client handles the rest)
    creds = Credentials(token=access_token)

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return service
