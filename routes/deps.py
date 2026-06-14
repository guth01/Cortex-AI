"""
Shared dependencies used across all route modules.

Provides database access and user authentication dependencies.
"""

from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import get_current_user_email
from slowapi import Limiter
from slowapi.util import get_remote_address

# Global rate limiter
limiter = Limiter(key_func=get_remote_address)


# Global database reference — set by server.py on startup
_database: AsyncIOMotorDatabase = None


def set_database(db: AsyncIOMotorDatabase):
    """Called once by server.py after MongoDB connects."""
    global _database
    _database = db


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get the database instance."""
    if _database is None:
        raise RuntimeError("Database not initialized. Server startup incomplete.")
    return _database


def serialize_mongo_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


async def get_current_user(
    email: str = Depends(get_current_user_email),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Get the current authenticated user from the database.

    This is the main dependency used in all protected routes.
    """
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return serialize_mongo_doc(user)
