"""
Subject routes — create, list, delete subjects.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from models import SubjectCreate, SubjectResponse
from routes.deps import get_db, get_current_user, serialize_mongo_doc

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Create a new subject.

    Protected route — requires authentication.
    """
    subject_doc = {
        "user_id": current_user["id"],
        "name": subject_data.name,
        "exam_date": subject_data.exam_date,
        "created_at": datetime.utcnow(),
    }

    result = await db.subjects.insert_one(subject_doc)
    subject_doc["_id"] = result.inserted_id

    return SubjectResponse(**serialize_mongo_doc(subject_doc))


@router.get("", response_model=List[SubjectResponse])
async def get_subjects(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get all subjects for the current user.

    Protected route — requires authentication.
    """
    subjects = await db.subjects.find(
        {"user_id": current_user["id"]}
    ).sort("created_at", -1).to_list(length=None)

    return [SubjectResponse(**serialize_mongo_doc(s)) for s in subjects]


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Delete a subject.

    Protected route — requires authentication.
    Only the owner can delete their subject.
    """
    try:
        object_id = ObjectId(subject_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subject ID format",
        )

    subject = await db.subjects.find_one({
        "_id": object_id,
        "user_id": current_user["id"],
    })

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found or you don't have permission to delete it",
        )

    await db.subjects.delete_one({"_id": object_id})
    return None
