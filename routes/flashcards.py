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

from routes.deps import get_db, get_current_user, serialize_mongo_doc

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


class ReviewRequest(BaseModel):
    quality: int  # 0-5 (SM-2 scale). 5=perfect, 4=correct, 3=correct effort, 2=wrong easy, 1=wrong, 0=blackout


def sm2_next_review(easiness: float, interval: int, repetitions: int, quality: int):
    """
    SM-2 spaced repetition algorithm.
    Returns (new_easiness, new_interval, new_repetitions, next_review_date).
    """
    # Clamp quality
    quality = max(0, min(5, quality))

    if quality < 3:
        # Failed — reset
        new_repetitions = 0
        new_interval = 1
    else:
        new_repetitions = repetitions + 1
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * easiness)

    # Update easiness factor
    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    next_review = datetime.utcnow() + timedelta(days=new_interval)
    return new_easiness, new_interval, new_repetitions, next_review


@router.get("", response_model=List[dict])
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

    cards = await db.flashcards.find(query).sort("next_review", 1).to_list(length=None)
    return [serialize_mongo_doc(c) for c in cards]


@router.post("/{flashcard_id}/review", status_code=status.HTTP_200_OK)
async def review_flashcard(
    flashcard_id: str,
    body: ReviewRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Submit a review for a flashcard using SM-2 spaced repetition.

    quality: 0-5 (5=perfect, 1=forgot, 3=correct with effort)
    Updates easiness_factor, interval, repetitions, and next_review date.
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

    new_ef, new_interval, new_reps, next_review = sm2_next_review(
        easiness=card.get("easiness_factor", 2.5),
        interval=card.get("interval", 0),
        repetitions=card.get("repetitions", 0),
        quality=body.quality,
    )

    await db.flashcards.update_one(
        {"_id": card_oid},
        {
            "$set": {
                "easiness_factor": new_ef,
                "interval": new_interval,
                "repetitions": new_reps,
                "next_review": next_review,
                "last_reviewed": datetime.utcnow(),
            }
        },
    )

    return {
        "id": flashcard_id,
        "next_review": next_review.isoformat(),
        "interval": new_interval,
        "easiness_factor": round(new_ef, 3),
        "repetitions": new_reps,
    }
