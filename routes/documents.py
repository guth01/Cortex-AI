"""
Document routes — upload, list, delete documents.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from models import DocumentResponse
from routes.deps import get_db, get_current_user, serialize_mongo_doc

router = APIRouter(prefix="/documents", tags=["documents"])

# Upload configuration
UPLOAD_DIR = Path("./uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "txt"}


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    subject_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Upload a document file (PDF, DOCX, MD, TXT).

    - subject_id is optional (can organize later)
    - Validates file type and size
    - Saves to disk at /uploads/{user_id}/{uuid}_{filename}
    - Stores metadata in MongoDB documents collection

    Protected route — requires authentication.
    """
    # Validate subject if provided
    if subject_id:
        try:
            subject_obj_id = ObjectId(subject_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subject ID format",
            )

        subject = await db.subjects.find_one({
            "_id": subject_obj_id,
            "user_id": current_user["id"],
        })

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission to upload to it",
            )

    # Validate file type
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content and validate size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Create user-specific upload directory
    user_upload_dir = UPLOAD_DIR / current_user["id"]
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    file_uuid = str(uuid.uuid4())
    unique_filename = f"{file_uuid}_{file.filename}"
    file_path = user_upload_dir / unique_filename

    # Save file to disk
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    # Try to parse file to get page count (for PDFs)
    page_count = None
    try:
        if file_ext == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            page_count = len(reader.pages)
    except Exception:
        pass  # Not critical if parsing fails

    # Create document record in MongoDB
    document_doc = {
        "user_id": current_user["id"],
        "subject_id": subject_id,
        "filename": file.filename,
        "file_path": str(file_path),
        "source_type": file_ext,
        "file_size": file_size,
        "uploaded_at": datetime.utcnow(),
        "page_count": page_count,
    }

    result = await db.documents.insert_one(document_doc)
    document_doc["_id"] = result.inserted_id

    return DocumentResponse(**serialize_mongo_doc(document_doc))


@router.get("", response_model=List[DocumentResponse])
async def get_documents(
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get all documents for the current user.

    Optional filtering by subject_id.
    Protected route — requires authentication.
    """
    query = {"user_id": current_user["id"]}

    if subject_id:
        query["subject_id"] = subject_id

    documents = await db.documents.find(query).sort("uploaded_at", -1).to_list(length=None)

    return [DocumentResponse(**serialize_mongo_doc(d)) for d in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Delete a document.

    Deletes both the MongoDB record and the file from disk.
    Protected route — requires authentication.
    Only the owner can delete their document.
    """
    try:
        object_id = ObjectId(document_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )

    document = await db.documents.find_one({
        "_id": object_id,
        "user_id": current_user["id"],
    })

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have permission to delete it",
        )

    # Delete file from disk
    file_path = Path(document["file_path"])
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"Warning: Failed to delete file {file_path}: {e}")

    await db.documents.delete_one({"_id": object_id})
    return None
