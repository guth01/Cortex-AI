"""
LangGraph nodes — each node transforms the AgentState.

Every node is a plain async function that takes state and returns
a dict of state fields to update (LangGraph merges them).

LLM used: Gemini (via langchain-google-genai).

Day 5 additions:
  gap_analysis_node       — runs knowledge_gap_analysis, stores result in state
  study_plan_builder_node — calls generate_study_plan, stores proposed events
  calendar_node           — creates Google Calendar events for each proposed session
  flashcard_generator_node — calls create_flashcards, stores result in state
  revision_sheet_node     — calls generate_exam_revision_sheet, stores document

Routing additions:
  route_by_content_type   — after planner: flashcards/revision vs generic synthesis
  route_by_calendar_auth  — checks if user has Google OAuth tokens in Atlas
  Updated route_by_intent — study_planning now routes to gap_analysis (not planner)
"""

import os
import re
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState
from agent.tools import (
    search_notes,
    fetch_wikipedia_summary,
    knowledge_gap_analysis,
    generate_study_plan,
    create_flashcards,
    generate_exam_revision_sheet,
    create_study_session_event,
)


# ============================================================================
# Shared LLM instance (Gemini)
# ============================================================================

def _get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """Get a configured Gemini LLM instance."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=temperature,
    )


# ============================================================================
# RouterNode — classifies the user's intent
# ============================================================================

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a student study assistant.

Classify the user's message into exactly ONE of these intents:
- rag_query       → asking about content from their notes/documents (explain, what is, how does, etc.)
- content_generation → asking to create study material (flashcards, quiz, summary, mind map, revision sheet, etc.)
- study_planning  → asking about schedules, study plans, what to study, time management, exam prep
- session_end     → wants to end the session (goodbye, done, quit, stop, finish)
- chitchat        → casual conversation, greetings, unrelated to studying

Respond with ONLY the intent label, nothing else. No punctuation, no explanation.
Examples:
  User: "explain virtual memory" → rag_query
  User: "make me 10 flashcards on recursion" → content_generation
  User: "create a study plan for my exam" → study_planning
  User: "plan my OS revision, exam is April 15" → study_planning
  User: "generate a revision sheet for databases" → content_generation
  User: "hi there!" → chitchat
  User: "I'm done for today" → session_end"""


async def router_node(state: AgentState) -> dict:
    """
    RouterNode: Classify the latest user message into an intent.
    Fast, cheap call — no context needed, just the last message.
    """
    print("[NODE:router] Classifying intent...")

    llm = _get_llm(temperature=0.0)  # deterministic classification

    last_message = state["messages"][-1]["content"] if state["messages"] else ""

    response = await llm.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=last_message),
    ])

    raw_intent = response.content.strip().lower()

    # Validate — fall back to rag_query if model hallucinates
    valid_intents = {"rag_query", "content_generation", "study_planning", "session_end", "chitchat"}
    intent = raw_intent if raw_intent in valid_intents else "rag_query"

    print(f"[NODE:router] intent='{intent}' (raw='{raw_intent}')")
    return {"intent": intent}


# ============================================================================
# RAGNode — semantic search over session's ChromaDB
# ============================================================================

CONFIDENCE_THRESHOLD = 0.45  # below this → fall through to Wikipedia


async def rag_node(state: AgentState) -> dict:
    """
    RAGNode: Perform semantic search using the user's notes.
    Sets retrieved_chunks and chunk_confidence in state.
    """
    print("[NODE:rag] Searching notes...")

    last_message = state["messages"][-1]["content"] if state["messages"] else ""
    session_id = state["session_id"]

    result = search_notes(query=last_message, session_id=session_id, top_k=5)

    chunks = result.get("chunks", [])
    confidence = result.get("confidence", 0.0)

    print(f"[NODE:rag] Retrieved {len(chunks)} chunks, confidence={confidence:.3f}")
    return {
        "retrieved_chunks": chunks,
        "chunk_confidence": confidence,
    }


# ============================================================================
# WikipediaNode — fallback when RAG confidence is insufficient
# ============================================================================

async def wikipedia_node(state: AgentState) -> dict:
    """
    WikipediaNode: Fetch Wikipedia summary when notes lack sufficient info.
    Appends result to tool_results.
    """
    print("[NODE:wikipedia] Fetching Wikipedia fallback...")

    # Extract the core topic from the last message
    last_message = state["messages"][-1]["content"] if state["messages"] else ""

    # Ask Gemini to extract just the topic (quick call)
    llm = _get_llm(temperature=0.0)
    topic_response = await llm.ainvoke([
        SystemMessage(content="Extract the core topic being asked about. Return ONLY the topic name, 1-5 words, no punctuation."),
        HumanMessage(content=last_message),
    ])
    topic = topic_response.content.strip()
    print(f"[NODE:wikipedia] Extracted topic: '{topic}'")

    wiki_result = fetch_wikipedia_summary(topic)

    tool_results = dict(state.get("tool_results") or {})
    tool_results["wikipedia"] = wiki_result

    print(f"[NODE:wikipedia] Wikipedia found={wiki_result['found']}")
    return {"tool_results": tool_results}


# ============================================================================
# PlannerNode — breaks complex requests into steps
# ============================================================================

PLANNER_SYSTEM_PROMPT = """You are a study session planner. Given a student's request, break it into an ordered list of concrete steps.

Your plan steps should be SHORT action descriptions (5-10 words each).
Return ONLY a numbered list of steps, nothing else.

For content_generation requests, typical steps:
1. Search notes for relevant content
2. Identify key concepts to cover
3. Generate the requested content type
4. Format the output

Return 3-6 steps maximum."""


async def planner_node(state: AgentState) -> dict:
    """
    PlannerNode: Decompose complex content_generation requests into an execution plan.
    Used ONLY for content_generation intent (study_planning now goes to gap_analysis).
    """
    print("[NODE:planner] Building execution plan...")

    llm = _get_llm(temperature=0.2)
    last_message = state["messages"][-1]["content"] if state["messages"] else ""

    response = await llm.ainvoke([
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"Request: {last_message}"),
    ])

    # Parse numbered list into clean step strings
    raw_plan = response.content.strip()
    lines = raw_plan.split("\n")
    steps = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                steps.append(clean)

    if not steps:
        steps = ["Search notes for relevant content", "Generate response"]

    print(f"[NODE:planner] Plan: {steps}")
    return {"plan": steps}


# ============================================================================
# GapAnalysisNode — knowledge gap analysis (Day 5)
# ============================================================================

async def gap_analysis_node(state: AgentState) -> dict:
    """
    GapAnalysisNode: Analyze which topics are covered/missing in the student's notes.

    Called as the first node for study_planning intent.
    Stores results in tool_results["gap_analysis"].
    """
    print("[NODE:gap_analysis] Running knowledge gap analysis...")

    session_id = state["session_id"]
    subject_name = state.get("subject_name") or "default"

    gap_result = knowledge_gap_analysis(
        session_id=session_id,
        subject_name=subject_name,
    )

    tool_results = dict(state.get("tool_results") or {})
    tool_results["gap_analysis"] = gap_result

    print(
        f"[NODE:gap_analysis] covered={len(gap_result.get('well_covered', []))}, "
        f"shallow={len(gap_result.get('shallow', []))}, "
        f"missing={len(gap_result.get('missing', []))}"
    )
    return {"tool_results": tool_results}


# ============================================================================
# StudyPlanBuilderNode — generates proposed study plan (Day 5)
# ============================================================================

# Prompt to extract exam date + subject name from user message
EXTRACT_PLAN_PROMPT = """Extract study planning information from the student's message.
Return ONLY a JSON object with exactly these fields:
  - "exam_date": the exam date as a string (e.g. "April 15", "2025-04-15") or null if not mentioned
  - "subject": the subject/topic name or null if not mentioned

Examples:
  "plan my OS revision, exam is April 15" → {"exam_date": "April 15", "subject": "Operating Systems"}
  "I have a databases exam on June 3rd" → {"exam_date": "June 3", "subject": "databases"}
  "help me study" → {"exam_date": null, "subject": null}

Return ONLY the JSON, no markdown, no explanation."""


async def study_plan_builder_node(state: AgentState) -> dict:
    """
    StudyPlanBuilderNode: Generate a proposed study schedule.

    1. Extracts exam_date and subject_name from the user message
    2. Calls generate_study_plan to build weighted session list
    3. Stores proposed events in state
    4. Sets awaiting_confirmation = True (triggers interrupt before CalendarNode)
    """
    print("[NODE:study_plan_builder] Building study plan...")

    import json as _json
    llm = _get_llm(temperature=0.0)
    last_message = state["messages"][-1]["content"] if state["messages"] else ""

    # Step 1: Extract exam date + subject from the message
    extract_response = await llm.ainvoke([
        SystemMessage(content=EXTRACT_PLAN_PROMPT),
        HumanMessage(content=last_message),
    ])

    raw = extract_response.content.strip()
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")

    try:
        extracted = _json.loads(clean)
    except Exception:
        extracted = {"exam_date": None, "subject": None}

    exam_date = extracted.get("exam_date") or state.get("exam_date") or "2025-12-31"
    subject_name = (
        extracted.get("subject")
        or state.get("subject_name")
        or "General"
    )

    print(f"[NODE:study_plan_builder] exam_date='{exam_date}', subject='{subject_name}'")

    # Step 2: Generate study plan
    plan_result = generate_study_plan(
        session_id=state["session_id"],
        subject_name=subject_name,
        exam_date=exam_date,
    )

    proposed_events = plan_result.get("proposed_events", [])

    # Update tool_results with full plan data
    tool_results = dict(state.get("tool_results") or {})
    tool_results["study_plan"] = plan_result

    print(f"[NODE:study_plan_builder] {len(proposed_events)} sessions proposed")
    return {
        "proposed_calendar_events": proposed_events,
        "awaiting_confirmation": True,
        "exam_date": exam_date,
        "subject_name": subject_name,
        "tool_results": tool_results,
    }


# ============================================================================
# CalendarNode — creates Google Calendar events (Day 5, interrupt fires before this)
# ============================================================================

async def calendar_node(state: AgentState) -> dict:
    """
    CalendarNode: Create Google Calendar events for each proposed study session.

    This node fires ONLY after the user confirms the plan via POST /confirm-plan.
    LangGraph interrupt fires BEFORE this node — execution resumes here on confirm.

    Calls create_study_session_event for each event in proposed_calendar_events.
    Stores created event links in tool_results["calendar_events"].
    """
    print("[NODE:calendar] Creating Google Calendar events...")

    from routes.deps import get_db
    db = get_db()

    user_id = state["user_id"]
    proposed_events = state.get("proposed_calendar_events", [])

    if not proposed_events:
        print("[NODE:calendar] No events to create")
        tool_results = dict(state.get("tool_results") or {})
        tool_results["calendar_events"] = []
        return {
            "tool_results": tool_results,
            "awaiting_confirmation": False,
        }

    created_events = []
    failed_events = []

    for event in proposed_events:
        result = await create_study_session_event(
            user_id=user_id,
            subject=f"{event.get('subject', 'Study')} — {event.get('topic', '')}",
            date=event["date"],
            duration_minutes=event.get("duration_minutes", 60),
            db=db,
        )

        if "error" in result:
            print(f"[NODE:calendar] Failed to create event on {event['date']}: {result['error']}")
            failed_events.append({**event, "error": result["error"]})
        else:
            created_events.append(result)
            print(f"[NODE:calendar] Created: {result.get('html_link', '')}")

    tool_results = dict(state.get("tool_results") or {})
    tool_results["calendar_events"] = created_events
    if failed_events:
        tool_results["calendar_failed"] = failed_events

    print(f"[NODE:calendar] Done: {len(created_events)} created, {len(failed_events)} failed")
    return {
        "tool_results": tool_results,
        "awaiting_confirmation": False,
    }


# ============================================================================
# FlashcardGeneratorNode — generates and persists flashcards (Day 5)
# ============================================================================

# Prompt to extract topic + card count from user message
EXTRACT_FLASHCARD_PROMPT = """Extract flashcard generation parameters from the student's message.
Return ONLY a JSON object with exactly these fields:
  - "topic": the topic to create flashcards on (string)
  - "num_cards": number of cards requested (integer, default 10 if not specified)

Examples:
  "make me 5 flashcards on scheduling algorithms" → {"topic": "scheduling algorithms", "num_cards": 5}
  "create flashcards for recursion" → {"topic": "recursion", "num_cards": 10}
  "give me 20 cards on the French Revolution" → {"topic": "French Revolution", "num_cards": 20}

Return ONLY the JSON, no markdown, no explanation."""


async def flashcard_generator_node(state: AgentState) -> dict:
    """
    FlashcardGeneratorNode: Generate flashcards using RAG + Gemini and persist to Atlas.

    Extracts topic and num_cards from the user message, then calls create_flashcards.
    Stores result in tool_results["flashcards"].
    """
    print("[NODE:flashcard_generator] Generating flashcards...")

    import json as _json
    from routes.deps import get_db
    db = get_db()

    llm = _get_llm(temperature=0.2)
    last_message = state["messages"][-1]["content"] if state["messages"] else ""

    # Step 1: Extract topic + num_cards
    extract_response = await llm.ainvoke([
        SystemMessage(content=EXTRACT_FLASHCARD_PROMPT),
        HumanMessage(content=last_message),
    ])

    raw = extract_response.content.strip()
    clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")

    try:
        extracted = _json.loads(clean)
        topic = extracted.get("topic", "General Study Topic")
        num_cards = int(extracted.get("num_cards", 10))
        num_cards = max(1, min(num_cards, 30))  # cap between 1–30
    except Exception:
        topic = last_message[:50]
        num_cards = 10

    print(f"[NODE:flashcard_generator] topic='{topic}', num_cards={num_cards}")

    # Step 2: Create flashcards
    flashcard_result = await create_flashcards(
        topic=topic,
        num_cards=num_cards,
        session_id=state["session_id"],
        subject_id=state["subject_id"],
        user_id=state["user_id"],
        db=db,
        llm=llm,
    )

    tool_results = dict(state.get("tool_results") or {})
    tool_results["flashcards"] = flashcard_result

    print(f"[NODE:flashcard_generator] Created {flashcard_result.get('cards_created', 0)} flashcards")
    return {"tool_results": tool_results}


# ============================================================================
# RevisionSheetNode — generates exam revision document (Day 5)
# ============================================================================

async def revision_sheet_node(state: AgentState) -> dict:
    """
    RevisionSheetNode: Generate a structured exam revision sheet.

    Runs gap_analysis + summarize_topic for each topic, compiles markdown doc.
    Stores result in tool_results["revision_sheet"].
    """
    print("[NODE:revision_sheet] Generating revision sheet...")

    llm = _get_llm(temperature=0.3)

    # Cool down before starting — previous nodes (router, flashcard, synthesis)
    # may have consumed the 5 RPM budget. Wait 15s to let the window reset.
    print("[NODE:revision_sheet] Waiting 15s for API rate limit window reset...")
    import asyncio as _asyncio
    await _asyncio.sleep(15)

    subject_name = state.get("subject_name") or "General"

    # Step 2: Generate sheet (loops over topics + gap analysis)
    result = await generate_exam_revision_sheet(
        subject_id=state["subject_id"],
        session_id=state["session_id"],
        subject_name=subject_name,
        llm=llm,
    )

    tool_results = dict(state.get("tool_results") or {})
    tool_results["revision_sheet"] = result

    print(f"[NODE:revision_sheet] Done: {result.get('topics_covered', 0)} topics")
    return {"tool_results": tool_results}


# ============================================================================
# SynthesisNode — the ONLY node that produces the final answer
# ============================================================================

SYNTHESIS_SYSTEM_PROMPT = """You are a knowledgeable, encouraging study assistant named SKB (Study Knowledge Bot).

Your job is to give clear, accurate, and helpful responses to students.

RULES:
- Base your answer primarily on the provided notes/context
- If Wikipedia was used as fallback, mention it naturally ("According to Wikipedia...")
- If neither notes nor Wikipedia have info, use your general knowledge but say so
- Be conversational but educational
- Use markdown formatting: **bold** for key terms, bullet points for lists
- Keep responses focused and appropriately detailed for studying
- Never make up facts — if uncertain, say so"""


async def synthesis_node(state: AgentState) -> dict:
    """
    SynthesisNode: Generate the final response using all available context.
    This is the ONLY place the final answer text is produced.
    Handles all tool_results keys including Day 5 additions.
    """
    print("[NODE:synthesis] Generating final response...")

    llm = _get_llm(temperature=0.4)

    last_message = state["messages"][-1]["content"] if state["messages"] else ""
    chunks = state.get("retrieved_chunks") or []
    tool_results = state.get("tool_results") or {}
    intent = state.get("intent", "rag_query")
    plan = state.get("plan") or []

    # ---- Build context sections ----
    context_parts = []

    if chunks:
        notes_text = "\n\n---\n\n".join([
            f"[From: {c['metadata'].get('filename', 'notes')}]\n{c['content']}"
            for c in chunks
        ])
        confidence = state.get("chunk_confidence", 0.0)
        context_parts.append(f"## Notes from Student's Documents (confidence: {confidence:.0%})\n\n{notes_text}")

    wiki = tool_results.get("wikipedia", {})
    if wiki and wiki.get("found"):
        context_parts.append(
            f"## Wikipedia: {wiki['title']}\n\n{wiki['summary']}\nSource: {wiki.get('url', '')}"
        )

    gap = tool_results.get("gap_analysis", {})
    if gap:
        context_parts.append(
            f"## Knowledge Gap Analysis\n"
            f"- Well covered: {', '.join(gap.get('well_covered', [])) or 'none'}\n"
            f"- Needs work: {', '.join(gap.get('shallow', [])) or 'none'}\n"
            f"- Missing: {', '.join(gap.get('missing', [])) or 'none'}"
        )

    # Day 5: Study plan context (awaiting confirmation)
    study_plan = tool_results.get("study_plan", {})
    if study_plan and state.get("awaiting_confirmation"):
        proposed = study_plan.get("proposed_events", [])
        exam_date = study_plan.get("exam_date", "")
        sessions_summary = "\n".join([
            f"  • {e['date']}: {e['topic']} ({e['duration_minutes']} min)"
            for e in proposed[:10]  # show first 10
        ])
        context_parts.append(
            f"## Proposed Study Plan ({len(proposed)} sessions until {exam_date})\n{sessions_summary}"
        )

    # Day 5: Calendar events just created
    calendar_events = tool_results.get("calendar_events", [])
    if calendar_events:
        links = "\n".join([
            f"  • {e.get('title', '')}: {e.get('html_link', 'no link')}"
            for e in calendar_events
        ])
        context_parts.append(f"## Google Calendar Events Created\n{links}")

    # Day 5: Flashcards just generated
    flashcard_data = tool_results.get("flashcards", {})
    if flashcard_data and flashcard_data.get("cards_created", 0) > 0:
        cards = flashcard_data.get("cards", [])
        cards_text = "\n".join([
            f"  **Q:** {c['question']}\n  **A:** {c['answer']}"
            for c in cards[:5]  # preview first 5
        ])
        context_parts.append(
            f"## Flashcards Generated ({flashcard_data['cards_created']} total)\n{cards_text}"
        )

    # Day 5: Revision sheet
    revision_sheet = tool_results.get("revision_sheet", {})
    if revision_sheet and revision_sheet.get("document"):
        doc_preview = revision_sheet["document"][:1500]  # first 1500 chars
        context_parts.append(f"## Revision Sheet (Preview)\n{doc_preview}")

    context_block = "\n\n".join(context_parts) if context_parts else "No specific context available — using general knowledge."

    # ---- Build intent-aware user prompt ----
    if intent == "chitchat":
        user_prompt = f"Student said: {last_message}\n\nRespond naturally and warmly."

    elif state.get("awaiting_confirmation") and study_plan:
        # Study plan is ready — present it for confirmation
        proposed = study_plan.get("proposed_events", [])
        exam_date = study_plan.get("exam_date", "")
        user_prompt = f"""Student request: {last_message}

I've analyzed their knowledge gaps and created a study plan.

{context_block}

Present the proposed study plan clearly:
- Show the key sessions (group by week if many)
- Explain WHY certain topics are prioritized (based on gap analysis)
- End with: "Reply **confirm** to add these to your Google Calendar, or let me know if you'd like to adjust the plan."

Keep the tone encouraging and motivating."""

    elif flashcard_data and flashcard_data.get("cards_created", 0) > 0:
        # Flashcards were just created
        user_prompt = f"""Student request: {last_message}

{context_block}

Present the flashcards in a clear, readable format. Show ALL {flashcard_data.get('cards_created', 0)} cards.
Format each as:
**Card N: [card_type]**
Q: [question]
A: [answer]

End with an encouraging message about using the cards for spaced repetition."""

    elif calendar_events:
        # Events were created
        user_prompt = f"""The study sessions have been added to Google Calendar!

{context_block}

Summarize what was created, list the calendar links, and give an encouraging message about following the study schedule."""

    elif revision_sheet and revision_sheet.get("document"):
        # Return the full revision sheet
        user_prompt = f"Return the following revision document verbatim:\n\n{revision_sheet['document']}"

    elif plan:
        plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
        user_prompt = f"""Student request: {last_message}

Execution plan:
{plan_str}

Context:
{context_block}

Execute the plan and fulfill the student's request completely."""
    else:
        user_prompt = f"""Student question: {last_message}

Context from notes and tools:
{context_block}

Answer the question using the context above."""

    response = await llm.ainvoke([
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    answer = response.content if hasattr(response, "content") else str(response)
    print(f"[NODE:synthesis] Generated response ({len(answer)} chars)")

    return {"response": answer}


# ============================================================================
# Edge routing functions (used by LangGraph conditional edges)
# ============================================================================

def route_by_intent(state: AgentState) -> Literal["rag", "planner", "gap_analysis", "synthesis"]:
    """
    Map intent → next node after router.

    study_planning now routes to gap_analysis (not planner).
    content_generation still routes to planner.
    """
    intent = state.get("intent", "rag_query")
    routes = {
        "rag_query": "rag",
        "content_generation": "planner",
        "study_planning": "gap_analysis",   # Day 5: new pipeline
        "session_end": "synthesis",
        "chitchat": "synthesis",
    }
    return routes.get(intent, "rag")


def route_by_confidence(state: AgentState) -> Literal["sufficient", "insufficient"]:
    """After RAG, decide whether to synthesize or fall back to Wikipedia."""
    confidence = state.get("chunk_confidence", 0.0)
    chunks = state.get("retrieved_chunks") or []

    if not chunks or confidence < CONFIDENCE_THRESHOLD:
        print(f"[EDGE:confidence] {confidence:.3f} < {CONFIDENCE_THRESHOLD} -> insufficient -> Wikipedia")
        return "insufficient"

    print(f"[EDGE:confidence] {confidence:.3f} >= {CONFIDENCE_THRESHOLD} -> sufficient -> synthesis")
    return "sufficient"


def route_by_content_type(state: AgentState) -> Literal["flashcard_generator", "revision_sheet", "rag"]:
    """
    After PlannerNode (content_generation intent), decide which specialist node to use.

    Detects flashcard and revision sheet requests from the last message.
    Falls back to rag (which then goes to synthesis) for everything else.
    """
    last_message = (state["messages"][-1]["content"] if state["messages"] else "").lower()

    flashcard_keywords = {"flashcard", "flash card", "cards", "quiz cards", "anki"}
    revision_keywords = {"revision sheet", "revision document", "cheat sheet", "study sheet", "summary sheet"}

    if any(kw in last_message for kw in flashcard_keywords):
        print("[EDGE:content_type] → flashcard_generator")
        return "flashcard_generator"

    if any(kw in last_message for kw in revision_keywords):
        print("[EDGE:content_type] → revision_sheet")
        return "revision_sheet"

    print("[EDGE:content_type] → rag (generic content generation)")
    return "rag"


async def route_by_calendar_auth(state: AgentState) -> Literal["has_auth", "no_auth"]:
    """
    Check if the user has Google OAuth tokens linked in Atlas.
    Returns 'has_auth' if tokens exist, 'no_auth' otherwise.
    """
    from routes.deps import get_db
    from bson import ObjectId

    user_id = state["user_id"]
    try:
        db = get_db()
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("google_access_token"):
            print(f"[EDGE:calendar_auth] user {user_id} → has_auth")
            return "has_auth"
    except Exception as e:
        print(f"[EDGE:calendar_auth] Error checking auth: {e}")

    print(f"[EDGE:calendar_auth] user {user_id} → no_auth")
    return "no_auth"
