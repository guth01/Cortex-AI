"""
Chat route — POST /chat/{session_id}

Flow:
1. Verify session is active in Atlas
2. Verify ChromaDB collection exists
3. Append user message to Atlas transcript
4. Invoke LangGraph agent (with thread_id for checkpointer)
5. Stream response back via SSE (Server-Sent Events)
6. If judge verdict is PARTIAL/INSUFFICIENT → emit fallback_choice_pending event
7. If awaiting_confirmation (study plan) → emit plan_pending event
8. Append assistant response to Atlas transcript

Endpoints:
  POST /chat/{session_id}                    — main chat (streaming SSE)
  POST /chat/{session_id}/sync               — non-streaming variant (testing)
  POST /chat/{session_id}/choose-fallback    — resume after fallback choice
  POST /sessions/{session_id}/confirm-plan   — resume after study plan confirmation
"""

import json
import asyncio
from datetime import datetime
from typing import Optional

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


# ============================================================================
# In-memory stores
# key: session_id  →  value: metadata dict
# ============================================================================
_pending_plans: dict = {}          # Waiting for study plan confirmation
_pending_fallbacks: dict = {}      # Waiting for fallback strategy choice


# ============================================================================
# Pydantic models
# ============================================================================

class ChatMessage(BaseModel):
    message: str


class ConfirmPlanRequest(BaseModel):
    action: str = "confirm"   # "confirm" or "reject"


class FallbackChoiceRequest(BaseModel):
    strategy: str             # "gemini" or "tavily"


# ============================================================================
# SSE helper — yields Server-Sent Events
# ============================================================================

def sse_event(data: dict, event: str = "message") -> str:
    """Format a dict as an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ============================================================================
# Main stream_agent_response generator
# ============================================================================

async def stream_agent_response(
    message: str,
    session_id: str,
    user_id: str,
    subject_id: str,
    subject_name: str,
    topics: list,
    transcript: list,
    db: AsyncIOMotorDatabase,
    session_oid: ObjectId,
):
    """
    Generator function that:
    1. Sends SSE events as the agent progresses through nodes
    2. Detects fallback interrupt (PARTIAL/INSUFFICIENT) → emits fallback_choice_pending
    3. Detects plan interrupt (study_planning) → emits plan_pending
    4. Saves the final response to Atlas transcript
    """
    yield sse_event({"type": "start", "session_id": session_id}, event="start")

    # Build initial state for LangGraph
    history = transcript[-10:] if len(transcript) > 10 else transcript

    initial_state: AgentState = {
        "messages": history + [{"role": "user", "content": message}],
        "session_id": session_id,
        "user_id": user_id,
        "subject_id": subject_id,
        "intent": "",
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
        "subject_name": subject_name,
        "topics": topics,
    }

    # Thread config — required for MemorySaver checkpointer
    thread_config = {"configurable": {"thread_id": session_id}}

    # ---- Stream intermediate node progress ----
    try:
        async for event in study_agent.astream(initial_state, config=thread_config):
            for node_name, updates in event.items():
                progress_data = {"type": "progress", "node": node_name}

                if "intent" in updates:
                    progress_data["intent"] = updates["intent"]
                    print(f"[CHAT] Router → intent='{updates['intent']}'")

                if "chunk_confidence" in updates:
                    progress_data["confidence"] = round(updates["chunk_confidence"], 3)
                    progress_data["chunks_found"] = len(updates.get("retrieved_chunks", []))

                # Sufficiency Judge progress
                if "judge_verdict" in updates:
                    progress_data["judge_verdict"] = updates["judge_verdict"]
                    progress_data["judge_reason"] = updates.get("judge_reason", "")
                    print(f"[CHAT] Judge → verdict='{updates['judge_verdict']}'")

                if "tool_results" in updates:
                    tr = updates["tool_results"]
                    if "gap_analysis" in tr:
                        gap = tr["gap_analysis"]
                        progress_data["gap_analysis"] = {
                            "well_covered": len(gap.get("well_covered", [])),
                            "shallow": len(gap.get("shallow", [])),
                            "missing": len(gap.get("missing", [])),
                        }
                    if "flashcards" in tr:
                        progress_data["flashcards_created"] = tr["flashcards"].get("cards_created", 0)
                    if "calendar_events" in tr:
                        progress_data["events_created"] = len(tr.get("calendar_events", []))

                if "proposed_calendar_events" in updates:
                    progress_data["events_proposed"] = len(updates["proposed_calendar_events"])

                if "web_results" in updates:
                    progress_data["web_results_count"] = len(updates.get("web_results", []))

                yield sse_event(progress_data, event="progress")

    except Exception as e:
        print(f"[CHAT] Agent stream error: {e}")
        yield sse_event({"type": "error", "detail": str(e)}, event="error")
        return

    # ---- Get full final state via ainvoke ----
    try:
        full_result = await study_agent.ainvoke(initial_state, config=thread_config)

        assistant_response = full_result.get("response", "I couldn't generate a response. Please try again.")
        final_intent = full_result.get("intent", "unknown")
        final_confidence = full_result.get("chunk_confidence", 0.0)
        chunks_used = len(full_result.get("retrieved_chunks", []))
        judge_verdict = full_result.get("judge_verdict")
        judge_reason = full_result.get("judge_reason")
        answer_source = full_result.get("answer_source", "notes")
        is_awaiting = full_result.get("awaiting_confirmation", False)
        proposed_events = full_result.get("proposed_calendar_events", [])

    except Exception as e:
        print(f"[CHAT] ainvoke error: {e}")
        assistant_response = f"I encountered an error: {str(e)}"
        final_intent = "error"
        final_confidence = 0.0
        chunks_used = 0
        judge_verdict = None
        judge_reason = None
        answer_source = "error"
        is_awaiting = False
        proposed_events = []

    # ---- If judge returned PARTIAL/INSUFFICIENT → emit fallback_choice_pending ----
    if judge_verdict in ("PARTIAL", "INSUFFICIENT") and not assistant_response.strip():
        # Graph was interrupted at await_fallback_node — no response yet
        _pending_fallbacks[session_id] = {
            "thread_id": session_id,
            "judge_verdict": judge_verdict,
            "judge_reason": judge_reason,
            "created_at": datetime.utcnow().isoformat(),
        }
        print(f"[CHAT] Fallback pending for session {session_id}, verdict={judge_verdict}")

        yield sse_event(
            {
                "type": "fallback_choice_pending",
                "verdict": judge_verdict,
                "reason": judge_reason,
                "message": (
                    "Your notes partially cover this topic. How would you like to supplement the answer?"
                    if judge_verdict == "PARTIAL"
                    else "This topic is not covered in your notes. How would you like to answer?"
                ),
                "options": [
                    {"id": "gemini", "label": "Use Gemini's knowledge"},
                    {"id": "tavily", "label": "Search the web (Tavily)"},
                ],
                "choose_url": f"/chat/{session_id}/choose-fallback",
            },
            event="fallback_choice_pending",
        )

        # Save user message to transcript (no assistant response yet — that comes after choice)
        now = datetime.utcnow()
        await db.sessions.update_one(
            {"_id": session_oid},
            {
                "$push": {
                    "transcript": {
                        "role": "user",
                        "content": message,
                        "timestamp": now,
                    }
                }
            },
        )

        yield sse_event({"type": "done"}, event="done")
        return

    # ---- If plan needs confirmation → emit plan_pending event ----
    if is_awaiting and proposed_events:
        _pending_plans[session_id] = {
            "thread_id": session_id,
            "proposed_events": proposed_events,
            "subject_name": full_result.get("subject_name", ""),
            "exam_date": full_result.get("exam_date", ""),
            "created_at": datetime.utcnow().isoformat(),
        }
        print(f"[CHAT] Plan pending for session {session_id} ({len(proposed_events)} events)")

        yield sse_event(
            {
                "type": "plan_pending",
                "proposed_events": proposed_events,
                "total_sessions": len(proposed_events),
                "confirm_url": f"/sessions/{session_id}/confirm-plan",
                "message": "Study plan is ready for your review. Confirm to add to Google Calendar.",
            },
            event="plan_pending",
        )

    # ---- Save to Atlas transcript ----
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
                                "judge_verdict": judge_verdict,
                                "judge_reason": judge_reason,
                                "answer_source": answer_source,
                                "awaiting_confirmation": is_awaiting,
                            },
                        },
                    ]
                }
            }
        },
    )

    print(f"[CHAT] Transcript saved. intent={final_intent}, verdict={judge_verdict}, source={answer_source}")

    # ---- Send final response ----
    yield sse_event(
        {
            "type": "response",
            "content": assistant_response,
            "metadata": {
                "intent": final_intent,
                "confidence": round(final_confidence, 3),
                "chunks_used": chunks_used,
                "judge_verdict": judge_verdict,
                "judge_reason": judge_reason,
                "answer_source": answer_source,
                "awaiting_confirmation": is_awaiting,
            },
        },
        event="response",
    )

    yield sse_event({"type": "done"}, event="done")


# ============================================================================
# Chat endpoint — POST /chat/{session_id}
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
    - progress events (which nodes fired, intent, judge verdict)
    - fallback_choice_pending event (if judge returns PARTIAL/INSUFFICIENT)
    - plan_pending event (if study_planning triggers calendar interrupt)
    - response event (final answer + metadata including answer_source)
    - done event

    Protected — requires authentication and active session ownership.
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
        raise HTTPException(
            status_code=400,
            detail=f"Session is not active (status: {session['status']}). Start a new session.",
        )

    try:
        get_session_collection(session_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail="ChromaDB collection missing for this session. The session may be corrupted.",
        )

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = body.message.strip()

    # Resolve subject name for study plan context
    subject_name = "General"
    subject_id = session.get("subject_id", "")
    if subject_id:
        try:
            subject_doc = await db.subjects.find_one({"_id": ObjectId(subject_id)})
            if subject_doc:
                subject_name = subject_doc.get("name", "General")
        except Exception:
            pass

    return StreamingResponse(
        stream_agent_response(
            message=message,
            session_id=session_id,
            user_id=current_user["id"],
            subject_id=subject_id,
            subject_name=subject_name,
            topics=session.get("topics", []),
            transcript=session.get("transcript", []),
            db=db,
            session_oid=session_oid,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Choose Fallback endpoint — POST /chat/{session_id}/choose-fallback
# ============================================================================

@router.post("/{session_id}/choose-fallback")
async def choose_fallback(
    session_id: str,
    body: FallbackChoiceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Resume the interrupted LangGraph after the user chooses a fallback strategy.

    When the Sufficiency Judge returns PARTIAL or INSUFFICIENT, the graph pauses
    at await_fallback_node and a fallback_choice_pending SSE event is sent.
    This endpoint resumes execution with the chosen strategy.

    Body:
        { "strategy": "gemini" | "tavily" }

    strategy="gemini":
        Graph resumes → synthesis_node generates answer using Gemini's knowledge

    strategy="tavily":
        Graph resumes → tavily_search_node → synthesis_node generates answer
        with clearly labelled web content

    Returns: SSE stream with progress + response + done events.
    """
    # Validate session ownership
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

    # Validate strategy
    strategy = body.strategy.strip().lower()
    if strategy not in ("gemini", "tavily"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy '{strategy}'. Must be 'gemini' or 'tavily'.",
        )

    # Check pending fallback exists
    pending = _pending_fallbacks.get(session_id)
    if not pending:
        raise HTTPException(
            status_code=404,
            detail="No pending fallback found for this session. Send a message first.",
        )

    judge_verdict = pending.get("judge_verdict", "INSUFFICIENT")
    judge_reason = pending.get("judge_reason", "")

    print(f"[CHOOSE-FALLBACK] session={session_id}, strategy={strategy}, verdict={judge_verdict}")

    async def _stream_fallback_response():
        yield sse_event(
            {"type": "start", "message": f"Generating answer using {strategy}..."},
            event="start",
        )

        thread_config = {"configurable": {"thread_id": session_id}}

        try:
            # Step 1: Patch fallback_strategy into the paused graph state.
            # This is the correct LangGraph pattern — update state THEN resume.
            await study_agent.aupdate_state(
                thread_config,
                {"fallback_strategy": strategy},
            )

            # Step 2: Pass None to resume from the await_fallback_node interrupt.
            # Passing a dict here would restart the graph from scratch.
            async for event in study_agent.astream(
                None,
                config=thread_config,
            ):
                for node_name, updates in event.items():
                    progress_data = {"type": "progress", "node": node_name}

                    if "web_results" in updates:
                        progress_data["web_results_count"] = len(updates.get("web_results", []))
                        print(f"[CHOOSE-FALLBACK] Tavily returned {len(updates.get('web_results', []))} results")

                    if "answer_source" in updates:
                        progress_data["answer_source"] = updates["answer_source"]

                    yield sse_event(progress_data, event="progress")

        except Exception as e:
            print(f"[CHOOSE-FALLBACK] Graph resume error: {e}")
            yield sse_event({"type": "error", "detail": str(e)}, event="error")
            return

        # Get final state — read it from the checkpointer (don't re-invoke)
        try:
            final_state = study_agent.get_state(thread_config).values
            assistant_response = final_state.get("response", "I couldn't generate a response.")
            answer_source = final_state.get("answer_source", strategy)
            final_confidence = final_state.get("chunk_confidence", 0.0)
            chunks_used = len(final_state.get("retrieved_chunks", []))
            web_results_count = len(final_state.get("web_results", []))

        except Exception as e:
            print(f"[CHOOSE-FALLBACK] ainvoke error after resume: {e}")
            assistant_response = f"I encountered an error generating the answer: {str(e)}"
            answer_source = "error"
            final_confidence = 0.0
            chunks_used = 0
            web_results_count = 0

        # Save to Atlas transcript
        now = datetime.utcnow()
        await db.sessions.update_one(
            {"_id": session_oid},
            {
                "$push": {
                    "transcript": {
                        "role": "assistant",
                        "content": assistant_response,
                        "timestamp": now,
                        "metadata": {
                            "intent": "rag_query",
                            "confidence": final_confidence,
                            "chunks_used": chunks_used,
                            "judge_verdict": judge_verdict,
                            "judge_reason": judge_reason,
                            "fallback_strategy": strategy,
                            "answer_source": answer_source,
                            "web_results_count": web_results_count,
                        },
                    }
                }
            },
        )

        # Clean up pending fallback
        _pending_fallbacks.pop(session_id, None)

        print(f"[CHOOSE-FALLBACK] Done. source={answer_source}, chars={len(assistant_response)}")

        yield sse_event(
            {
                "type": "response",
                "content": assistant_response,
                "metadata": {
                    "judge_verdict": judge_verdict,
                    "judge_reason": judge_reason,
                    "fallback_strategy": strategy,
                    "answer_source": answer_source,
                    "web_results_count": web_results_count,
                },
            },
            event="response",
        )
        yield sse_event({"type": "done"}, event="done")

    return StreamingResponse(
        _stream_fallback_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Confirm Plan endpoint — POST /sessions/{session_id}/confirm-plan
# ============================================================================

@router.post("/{session_id}/confirm-plan")
async def confirm_plan(
    session_id: str,
    body: ConfirmPlanRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Resume the interrupted LangGraph after the user confirms the study plan.

    If action == "confirm":
      - Resumes the graph from the interrupt point (before calendar_node)
      - CalendarNode fires, creates Google Calendar events
      - Returns SSE stream with calendar creation progress

    If action == "reject":
      - Clears the pending plan
      - Returns a JSON acknowledgment
    """
    # Validate session ownership
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

    # Check pending plan exists
    pending = _pending_plans.get(session_id)
    if not pending:
        raise HTTPException(
            status_code=404,
            detail="No pending study plan found for this session. Generate a plan first.",
        )

    # Handle rejection
    if body.action == "reject":
        del _pending_plans[session_id]
        return {"status": "rejected", "message": "Study plan discarded. Feel free to request a new one."}

    # ---- CONFIRM: Resume the graph ----
    async def _stream_calendar_creation():
        yield sse_event({"type": "start", "message": "Creating calendar events..."}, event="start")

        thread_config = {"configurable": {"thread_id": session_id}}

        try:
            # Resume graph from interrupt — LangGraph continues from where it stopped
            # (i.e., it now runs calendar_node → synthesis)
            async for event in study_agent.astream(None, config=thread_config):
                for node_name, updates in event.items():
                    progress_data = {"type": "progress", "node": node_name}

                    if "tool_results" in updates and "calendar_events" in updates["tool_results"]:
                        events_created = updates["tool_results"]["calendar_events"]
                        progress_data["events_created"] = len(events_created)
                        progress_data["links"] = [
                            e.get("html_link", "") for e in events_created if e.get("html_link")
                        ]

                    yield sse_event(progress_data, event="progress")

        except Exception as e:
            print(f"[CONFIRM-PLAN] Graph resume error: {e}")
            yield sse_event({"type": "error", "detail": str(e)}, event="error")
            return

        # Get final state — read it from the checkpointer (don't re-invoke)
        try:
            final_state = study_agent.get_state(thread_config).values
            calendar_events = final_state.get("tool_results", {}).get("calendar_events", [])
            assistant_response = final_state.get("response", "Your study sessions have been added to Google Calendar! 🎉")

        except Exception as e:
            print(f"[CONFIRM-PLAN] ainvoke error after resume: {e}")
            calendar_events = []
            assistant_response = "Calendar events created. Check your Google Calendar."

        # Save confirmation to Atlas transcript
        now = datetime.utcnow()
        await db.sessions.update_one(
            {"_id": session_oid},
            {
                "$push": {
                    "transcript": {
                        "$each": [
                            {"role": "user", "content": "[Confirmed study plan]", "timestamp": now},
                            {
                                "role": "assistant",
                                "content": assistant_response,
                                "timestamp": now,
                                "metadata": {
                                    "intent": "study_planning",
                                    "answer_source": "notes",
                                    "calendar_events_created": len(calendar_events),
                                },
                            },
                        ]
                    }
                }
            },
        )

        # Clean up pending plan
        _pending_plans.pop(session_id, None)

        yield sse_event(
            {
                "type": "response",
                "content": assistant_response,
                "calendar_events": calendar_events,
                "events_created": len(calendar_events),
            },
            event="response",
        )
        yield sse_event({"type": "done"}, event="done")

    return StreamingResponse(
        _stream_calendar_creation(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
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

    # Resolve subject name
    subject_name = "General"
    subject_id = session.get("subject_id", "")
    if subject_id:
        try:
            subject_doc = await db.subjects.find_one({"_id": ObjectId(subject_id)})
            if subject_doc:
                subject_name = subject_doc.get("name", "General")
        except Exception:
            pass

    history = session.get("transcript", [])[-10:]

    initial_state: AgentState = {
        "messages": history + [{"role": "user", "content": message}],
        "session_id": session_id,
        "user_id": current_user["id"],
        "subject_id": subject_id,
        "intent": "",
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
        "subject_name": subject_name,
        "topics": session.get("topics", []),
    }

    thread_id = session_id
    thread_config = {"configurable": {"thread_id": thread_id}}

    result = await study_agent.ainvoke(initial_state, config=thread_config)

    assistant_response = result.get("response", "No response generated.")
    final_intent = result.get("intent", "unknown")
    final_confidence = result.get("chunk_confidence", 0.0)
    chunks_used = len(result.get("retrieved_chunks", []))
    judge_verdict = result.get("judge_verdict")
    judge_reason = result.get("judge_reason")
    answer_source = result.get("answer_source", "notes")
    is_awaiting = result.get("awaiting_confirmation", False)
    proposed_events = result.get("proposed_calendar_events", [])

    # Store pending plan if applicable
    if is_awaiting and proposed_events:
        _pending_plans[session_id] = {
            "thread_id": thread_id,
            "proposed_events": proposed_events,
            "subject_name": result.get("subject_name", ""),
            "exam_date": result.get("exam_date", ""),
            "created_at": datetime.utcnow().isoformat(),
        }

    # Store pending fallback if graph was interrupted by await_fallback_node
    if judge_verdict in ("PARTIAL", "INSUFFICIENT") and not assistant_response.strip():
        _pending_fallbacks[session_id] = {
            "thread_id": thread_id,
            "judge_verdict": judge_verdict,
            "judge_reason": judge_reason,
            "created_at": datetime.utcnow().isoformat(),
        }

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
                                "judge_verdict": judge_verdict,
                                "judge_reason": judge_reason,
                                "answer_source": answer_source,
                                "awaiting_confirmation": is_awaiting,
                            },
                        },
                    ]
                }
            }
        },
    )

    response_body = {
        "response": assistant_response,
        "metadata": {
            "intent": final_intent,
            "confidence": round(final_confidence, 3),
            "chunks_used": chunks_used,
            "judge_verdict": judge_verdict,
            "judge_reason": judge_reason,
            "answer_source": answer_source,
            "awaiting_confirmation": is_awaiting,
        },
    }

    if is_awaiting and proposed_events:
        response_body["proposed_events"] = proposed_events
        response_body["confirm_url"] = f"/sessions/{session_id}/confirm-plan"

    if judge_verdict in ("PARTIAL", "INSUFFICIENT") and not assistant_response.strip():
        response_body["fallback_choice_pending"] = True
        response_body["choose_url"] = f"/chat/{session_id}/choose-fallback"
        response_body["options"] = ["gemini", "tavily"]

    return response_body
