"""
Chat route — POST /chat/{session_id}

Flow:
1. Verify session is active in Atlas
2. Verify ChromaDB collection exists
3. Append user message to Atlas transcript
4. Invoke LangGraph agent
5. Stream response back via SSE (Server-Sent Events)
6. Append assistant response to Atlas transcript
"""

import json
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel

from routes.deps import get_db, get_current_user
from db.chroma import get_session_collection
from agent.graph import study_agent
from agent.state import AgentState

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str


# ============================================================================
# SSE helper — yields Server-Sent Events
# ============================================================================

def sse_event(data: dict, event: str = "message") -> str:
    """Format a dict as an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_agent_response(
    message: str,
    session_id: str,
    user_id: str,
    subject_id: str,
    transcript: list,
    db: AsyncIOMotorDatabase,
    session_oid: ObjectId,
):
    """
    Generator function that:
    1. Sends SSE events as the agent progresses
    2. Saves the final response to Atlas transcript
    """
    # Send start event
    yield sse_event({"type": "start", "session_id": session_id}, event="start")

    # Build initial state for LangGraph
    # Include last 10 messages for context (keeps prompts manageable)
    history = transcript[-10:] if len(transcript) > 10 else transcript

    initial_state: AgentState = {
        "messages": history + [{"role": "user", "content": message}],
        "session_id": session_id,
        "user_id": user_id,
        "subject_id": subject_id,
        "intent": "",
        "retrieved_chunks": [],
        "chunk_confidence": 0.0,
        "tool_results": {},
        "plan": [],
        "response": "",
        "awaiting_confirmation": False,
        "proposed_calendar_events": [],
    }

    # Run agent (LangGraph is async-compatible)
    try:
        # Stream intermediate node updates
        final_state = None

        async for event in study_agent.astream(initial_state):
            # Each event is a dict: {node_name: state_updates}
            for node_name, updates in event.items():
                # Emit a progress event so the frontend can show thinking steps
                progress_data = {"type": "progress", "node": node_name}

                # Add intent when router fires
                if "intent" in updates:
                    progress_data["intent"] = updates["intent"]
                    print(f"[CHAT] Router → intent='{updates['intent']}'")

                # Add confidence when RAG fires
                if "chunk_confidence" in updates:
                    progress_data["confidence"] = round(updates["chunk_confidence"], 3)
                    progress_data["chunks_found"] = len(updates.get("retrieved_chunks", []))

                # Add Wikipedia info if it fires
                if "tool_results" in updates and "wikipedia" in updates["tool_results"]:
                    wiki = updates["tool_results"]["wikipedia"]
                    progress_data["wikipedia_used"] = wiki.get("found", False)
                    if wiki.get("found"):
                        progress_data["wikipedia_title"] = wiki.get("title", "")

                yield sse_event(progress_data, event="progress")

                # Track final state
                final_state = updates

        # Extract the final response
        # LangGraph returns the last complete state — we need to get the response field
        # astream gives us node-level updates, not the full state
        # Run one more time with ainvoke to get the full final state cleanly
        # (astream already ran it — we need the full result)

    except Exception as e:
        print(f"[CHAT] Agent error: {e}")
        yield sse_event({"type": "error", "detail": str(e)}, event="error")
        return

    # Get full final state via ainvoke (more reliable for extracting response)
    try:
        full_result = await study_agent.ainvoke(initial_state)
        assistant_response = full_result.get("response", "I couldn't generate a response. Please try again.")
        final_intent = full_result.get("intent", "unknown")
        final_confidence = full_result.get("chunk_confidence", 0.0)
        chunks_used = len(full_result.get("retrieved_chunks", []))
        wiki_used = bool(full_result.get("tool_results", {}).get("wikipedia", {}).get("found"))

    except Exception as e:
        print(f"[CHAT] ainvoke error: {e}")
        assistant_response = f"I encountered an error: {str(e)}"
        final_intent = "error"
        final_confidence = 0.0
        chunks_used = 0
        wiki_used = False

    # Save to Atlas transcript
    now = datetime.utcnow()
    await db.sessions.update_one(
        {"_id": session_oid},
        {
            "$push": {
                "transcript": {
                    "$each": [
                        {"role": "user", "content": message, "timestamp": now},
                        {
                            "role": "assistant",
                            "content": assistant_response,
                            "timestamp": now,
                            "metadata": {
                                "intent": final_intent,
                                "confidence": final_confidence,
                                "chunks_used": chunks_used,
                                "wikipedia_used": wiki_used,
                            },
                        },
                    ]
                }
            }
        },
    )

    print(f"[CHAT] Transcript saved. intent={final_intent}, confidence={final_confidence:.3f}")

    # Send the final response
    yield sse_event(
        {
            "type": "response",
            "content": assistant_response,
            "metadata": {
                "intent": final_intent,
                "confidence": round(final_confidence, 3),
                "chunks_used": chunks_used,
                "wikipedia_used": wiki_used,
            },
        },
        event="response",
    )

    # Send done event
    yield sse_event({"type": "done"}, event="done")


# ============================================================================
# Chat endpoint
# ============================================================================

@router.post("/{session_id}")
async def chat(
    session_id: str,
    body: ChatMessage,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Send a message to the study agent for an active session.

    Returns a streaming SSE response with:
    - progress events (which nodes fired, intent, confidence)
    - response event (final answer + metadata)
    - done event

    Protected — requires authentication and active session ownership.
    """
    # 1. Validate session_id format
    try:
        session_oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )

    # 2. Verify session is active and belongs to this user
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
            detail=f"Session is not active (status: {session['status']}). Start a new session.",
        )

    # 3. Verify ChromaDB collection exists
    try:
        get_session_collection(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ChromaDB collection missing for this session. The session may be corrupted.",
        )

    # 4. Validate message
    if not body.message or not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    message = body.message.strip()

    # 5. Stream the agent response
    return StreamingResponse(
        stream_agent_response(
            message=message,
            session_id=session_id,
            user_id=current_user["id"],
            subject_id=session["subject_id"],
            transcript=session.get("transcript", []),
            db=db,
            session_oid=session_oid,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering if proxied
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Non-streaming variant (for testing / simple clients)
# ============================================================================

@router.post("/{session_id}/sync")
async def chat_sync(
    session_id: str,
    body: ChatMessage,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Non-streaming chat — waits for full response and returns JSON.
    Useful for testing with curl/Postman without SSE support.
    Same validation as /chat/{session_id}.
    """
    try:
        session_oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    session = await db.sessions.find_one({
        "_id": session_oid,
        "user_id": current_user["id"],
    })

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail=f"Session is not active ({session['status']})")

    try:
        get_session_collection(session_id)
    except ValueError:
        raise HTTPException(status_code=409, detail="ChromaDB collection missing")

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = body.message.strip()

    history = session.get("transcript", [])[-10:]

    initial_state: AgentState = {
        "messages": history + [{"role": "user", "content": message}],
        "session_id": session_id,
        "user_id": current_user["id"],
        "subject_id": session["subject_id"],
        "intent": "",
        "retrieved_chunks": [],
        "chunk_confidence": 0.0,
        "tool_results": {},
        "plan": [],
        "response": "",
        "awaiting_confirmation": False,
        "proposed_calendar_events": [],
    }

    result = await study_agent.ainvoke(initial_state)

    assistant_response = result.get("response", "No response generated.")
    final_intent = result.get("intent", "unknown")
    final_confidence = result.get("chunk_confidence", 0.0)
    chunks_used = len(result.get("retrieved_chunks", []))
    wiki_used = bool(result.get("tool_results", {}).get("wikipedia", {}).get("found"))

    # Save to Atlas
    now = datetime.utcnow()
    await db.sessions.update_one(
        {"_id": session_oid},
        {
            "$push": {
                "transcript": {
                    "$each": [
                        {"role": "user", "content": message, "timestamp": now},
                        {
                            "role": "assistant",
                            "content": assistant_response,
                            "timestamp": now,
                            "metadata": {
                                "intent": final_intent,
                                "confidence": final_confidence,
                                "chunks_used": chunks_used,
                                "wikipedia_used": wiki_used,
                            },
                        },
                    ]
                }
            }
        },
    )

    return {
        "response": assistant_response,
        "metadata": {
            "intent": final_intent,
            "confidence": round(final_confidence, 3),
            "chunks_used": chunks_used,
            "wikipedia_used": wiki_used,
        },
    }
