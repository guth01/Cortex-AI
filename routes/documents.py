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

import cloudinary
import cloudinary.uploader
import os

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # some browsers send this for .md / .docx
}


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Validate MIME type (browsers send this — guards against renamed files)
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File MIME type '{content_type}' is not supported.",
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

    # Generate unique filename for Cloudinary
    file_uuid = str(uuid.uuid4())
    public_id = f"{file_uuid}_{file.filename}"
    folder_path = f"study_agent/{current_user['id']}"

    # Upload to Cloudinary
    try:
        # Use a thread so we don't block the async event loop
        import asyncio
        resource_type = "raw" if file_ext in ["pdf", "docx", "md", "txt", "csv"] else "auto"
        upload_result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            file_content,
            resource_type=resource_type,
            folder=folder_path,
            public_id=public_id
        )
        file_url = upload_result.get("secure_url")
        cloudinary_public_id = upload_result.get("public_id")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to Cloudinary: {str(e)}",
        )

    # Try to parse file to get page count (for PDFs)
    page_count = None
    try:
        if file_ext == "pdf":
            import fitz
            with fitz.open(stream=file_content, filetype="pdf") as doc:
                page_count = len(doc)
    except Exception:
        pass  # Not critical if parsing fails

    # Create document record in MongoDB
    document_doc = {
        "user_id": current_user["id"],
        "subject_id": subject_id,
        "filename": file.filename,
        "file_path": file_url,
        "cloudinary_public_id": cloudinary_public_id,
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

    # Delete file from Cloudinary if public_id exists, else fallback to local delete (for older docs)
    cloudinary_public_id = document.get("cloudinary_public_id")
    file_path = document.get("file_path", "")
    
    try:
        if cloudinary_public_id:
            import asyncio
            await asyncio.to_thread(cloudinary.uploader.destroy, cloudinary_public_id)
            print(f"[CLOUDINARY] Deleted {cloudinary_public_id}")
        else:
            # Fallback for old local files
            local_path = Path(file_path)
            if local_path.exists():
                local_path.unlink()
    except Exception as e:
        print(f"Warning: Failed to delete file {file_path}: {e}")

    await db.documents.delete_one({"_id": object_id})
    return None
