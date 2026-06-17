"""
Session routes — start, end, get, list sessions.
"""

from datetime import datetime
from typing import List, Optional
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from models import SessionCreate, SessionStartResponse, SessionResponse, SessionEndResponse
from routes.deps import get_db, get_current_user, serialize_mongo_doc
from utils.file_parser import load_documents
from utils.chunker import split_documents, split_documents_document_aware
from db.chroma import create_session_collection, delete_session_collection

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    session_data: SessionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Start a new study session.

    - Creates session record in MongoDB
    - Creates ephemeral ChromaDB collection
    - Loads selected documents: parse → chunk → embed → store in Chroma
    - Returns session ID and stats

    Protected route — requires authentication.
    """
    # 1. Validate subject_id
    try:
        subject_oid = ObjectId(session_data.subject_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subject ID format",
        )

    subject = await db.subjects.find_one({
        "_id": subject_oid,
        "user_id": current_user["id"],
    })
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    # 2. Validate document_ids
    if not session_data.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document ID is required",
        )

    documents = []
    for doc_id in session_data.document_ids:
        try:
            doc_oid = ObjectId(doc_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document ID format: {doc_id}",
            )

        doc = await db.documents.find_one({
            "_id": doc_oid,
            "user_id": current_user["id"],
        })
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {doc_id}",
            )
        documents.append(doc)

    # 3. Create session in MongoDB
    session_doc = {
        "user_id": current_user["id"],
        "subject_id": session_data.subject_id,
        "status": "active",
        "started_at": datetime.utcnow(),
        "documents_used": [str(d["_id"]) for d in documents],
        "topics": session_data.topics,
        "transcript": [],
        "summary": None,
    }
    result = await db.sessions.insert_one(session_doc)
    session_id = str(result.inserted_id)

    # 4. Create ChromaDB collection + load documents
    try:
        vectorstore = await asyncio.to_thread(create_session_collection, session_id)

        total_chunks = 0
        for doc in documents:
            # Check if file_path is a URL (Cloudinary)
            file_path_to_load = doc["file_path"]
            is_temp = False
            
            if file_path_to_load.startswith("http"):
                import tempfile
                import httpx
                import os
                
                suffix = f".{doc['source_type']}"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file_path = temp_file.name
                temp_file.close()
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(file_path_to_load)
                    resp.raise_for_status()
                    with open(temp_file_path, "wb") as f:
                        f.write(resp.content)
                
                file_path_to_load = temp_file_path
                is_temp = True
            
            try:
                # Load document with LangChain
                lc_docs = await asyncio.to_thread(
                    load_documents, file_path_to_load, doc["source_type"]
                )
            finally:
                # Clean up temporary file
                if is_temp:
                    import os
                    if os.path.exists(file_path_to_load):
                        os.remove(file_path_to_load)

            # Add metadata to each page/section
            for lc_doc in lc_docs:
                lc_doc.metadata.update({
                    "doc_id": str(doc["_id"]),
                    "filename": doc["filename"],
                    "subject_id": session_data.subject_id,
                })

            # Split into chunks
            if session_data.chunking_strategy == "document_aware":
                chunks = await asyncio.to_thread(split_documents_document_aware, lc_docs)
            else:
                chunks = await asyncio.to_thread(split_documents, lc_docs)

            # Add chunk index to metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata["chunk_index"] = i

            # Embed and store in ChromaDB
            if chunks:
                await asyncio.to_thread(vectorstore.add_documents, chunks)
                total_chunks += len(chunks)

        # 5. Store chunk count in session doc
        await db.sessions.update_one(
            {"_id": result.inserted_id},
            {"$set": {"chunk_count": total_chunks}},
        )

        return SessionStartResponse(
            session_id=session_id,
            docs_loaded=len(documents),
            chunk_count=total_chunks,
        )

    except Exception as e:
        # Cleanup on failure
        await asyncio.to_thread(delete_session_collection, session_id)
        await db.sessions.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "interrupted", "ended_at": datetime.utcnow()}},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load documents into session: {str(e)}",
        )


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    End an active study session.

    - Invokes the LangGraph session_end pipeline:
        router → evaluator → summary_node → save_node
    - save_node marks session completed, saves evaluation + summary, deletes Chroma collection.

    Protected route — requires authentication.
    """
    try:
        session_oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )

    session = await db.sessions.find_one({
        "_id": session_oid,
        "user_id": current_user["id"],
    })

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is already {session['status']}",
        )

    # ---- Invoke the session_end graph pipeline ----
    from agent.graph import study_agent
    from agent.state import AgentState

    transcript = session.get("transcript", [])

    initial_state: AgentState = {
        "messages": transcript + [{"role": "user", "content": "I'm done for today. Please end the session."}],
        "session_id": session_id,
        "user_id": current_user["id"],
        "subject_id": session.get("subject_id", ""),
        "intent": "session_end",
        "retrieved_chunks": [],
        "chunk_confidence": 0.0,
        "judge_verdict": None,
        "judge_reason": None,
        "fallback_strategy": None,
        "web_results": [],
        "answer_source": None,
        "tool_results": {},
        "plan": [],
        "response": "",
        "awaiting_confirmation": False,
        "proposed_calendar_events": [],
        "exam_date": None,
        "subject_name": None,
        "topics": session.get("topics", []),
        # Session end specific
        "transcript": transcript,
        "evaluation": None,
        "session_summary": None,
    }

    thread_config = {"configurable": {"thread_id": f"end-{session_id}"}}

    try:
        final_state = await study_agent.ainvoke(initial_state, config=thread_config)
        summary = final_state.get("session_summary") or "Session completed."
        evaluation = final_state.get("evaluation") or {}
        ended_at = datetime.utcnow()
    except Exception as e:
        print(f"[END_SESSION] Graph error: {e} — falling back to simple close")
        # Fallback: close session manually without evaluation
        ended_at = datetime.utcnow()
        summary = None
        evaluation = {}
        await db.sessions.update_one(
            {"_id": session_oid},
            {"$set": {"status": "completed", "ended_at": ended_at, "summary": summary}},
        )
        await asyncio.to_thread(delete_session_collection, session_id)

    # Re-read the session to get the updated ended_at written by save_node
    updated_session = await db.sessions.find_one({"_id": session_oid})
    ended_at = updated_session.get("ended_at", ended_at) if updated_session else ended_at

    return SessionEndResponse(
        session_id=session_id,
        status="completed",
        started_at=session["started_at"],
        ended_at=ended_at,
        summary=summary,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get a specific session's details.

    Returns transcript, summary, status, documents used.
    Protected route — requires authentication.
    """
    try:
        session_oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )

    session = await db.sessions.find_one({
        "_id": session_oid,
        "user_id": current_user["id"],
    })

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.get("summary") == "Session completed. (AI summary will be generated on Day 7)":
        session["summary"] = None

    return SessionResponse(**serialize_mongo_doc(session))


@router.get("", response_model=List[SessionResponse])
async def get_sessions(
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List all sessions for the current user.

    Optional filtering by subject_id.
    Protected route — requires authentication.
    """
    query = {"user_id": current_user["id"]}

    if subject_id:
        query["subject_id"] = subject_id

    sessions = await db.sessions.find(query).sort(
        "started_at", -1
    ).to_list(length=None)

    for s in sessions:
        if s.get("summary") == "Session completed. (AI summary will be generated on Day 7)":
            s["summary"] = None

    return [SessionResponse(**serialize_mongo_doc(s)) for s in sessions]
