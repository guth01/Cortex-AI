"""
Flashcard routes — list and review flashcards.
These cards are created by the agent's flashcard_node during sessions.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel

from models import FlashcardResponse
from routes.deps import get_db, get_current_user, serialize_mongo_doc

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("", response_model=List[FlashcardResponse])
async def get_flashcards(
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get all flashcards for the current user.
    Optional filtering by subject_id.
    Protected route — requires authentication.
    """
    query = {"user_id": current_user["id"]}
    if subject_id:
        query["subject_id"] = subject_id

    cards = await db.flashcards.find(query).sort("created_at", -1).to_list(length=None)
    return [serialize_mongo_doc(c) for c in cards]


@router.post("/{flashcard_id}/mark-done", status_code=status.HTTP_200_OK)
async def mark_flashcard_done(
    flashcard_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Mark a flashcard as done.
    Protected route — requires authentication.
    """
    try:
        card_oid = ObjectId(flashcard_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid flashcard ID format",
        )

    card = await db.flashcards.find_one({
        "_id": card_oid,
        "user_id": current_user["id"],
    })

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found",
        )

    await db.flashcards.update_one(
        {"_id": card_oid},
        {
            "$set": {
                "status": "done",
                "last_reviewed": datetime.utcnow(),
            }
        },
    )

    return {
        "id": flashcard_id,
        "status": "done",
    }
