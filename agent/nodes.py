"""
LangGraph nodes — each node transforms the AgentState.

Every node is a plain async function that takes state and returns
a dict of state fields to update (LangGraph merges them).

LLM used: Gemini (via langchain-google-genai).
"""

import os
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState
from agent.tools import (
    search_notes,
    fetch_wikipedia_summary,
    knowledge_gap_analysis,
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
        convert_system_message_to_human=True,  # Gemini requires this
    )


# ============================================================================
# RouterNode — classifies the user's intent
# ============================================================================

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a student study assistant.

Classify the user's message into exactly ONE of these intents:
- rag_query       → asking about content from their notes/documents (explain, what is, how does, etc.)
- content_generation → asking to create study material (flashcards, quiz, summary, mind map, etc.)
- study_planning  → asking about schedules, study plans, what to study, time management
- session_end     → wants to end the session (goodbye, done, quit, stop, finish)
- chitchat        → casual conversation, greetings, unrelated to studying

Respond with ONLY the intent label, nothing else. No punctuation, no explanation.
Examples:
  User: "explain virtual memory" → rag_query
  User: "make me 10 flashcards on recursion" → content_generation
  User: "create a study plan for my exam" → study_planning
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

For study_planning requests, typical steps:
1. Assess what topics need coverage
2. Estimate time requirements
3. Build a structured schedule
4. Add review checkpoints

Return 3-6 steps maximum."""


async def planner_node(state: AgentState) -> dict:
    """
    PlannerNode: Decompose complex requests into an execution plan.
    Used for content_generation and study_planning intents.
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
            # Remove numbering: "1. Step text" → "Step text"
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                steps.append(clean)

    if not steps:
        steps = ["Search notes for relevant content", "Generate response"]

    print(f"[NODE:planner] Plan: {steps}")
    return {"plan": steps}


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

    context_block = "\n\n".join(context_parts) if context_parts else "No specific context available — using general knowledge."

    # ---- Build intent-aware user prompt ----
    if intent == "chitchat":
        user_prompt = f"Student said: {last_message}\n\nRespond naturally and warmly."
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

def route_by_intent(state: AgentState) -> Literal["rag", "planner", "synthesis"]:
    """Map intent → next node after router."""
    intent = state.get("intent", "rag_query")
    routes = {
        "rag_query": "rag",
        "content_generation": "planner",
        "study_planning": "planner",
        "session_end": "synthesis",
        "chitchat": "synthesis",
    }
    return routes.get(intent, "rag")


def route_by_confidence(state: AgentState) -> Literal["sufficient", "insufficient"]:
    """After RAG, decide whether to synthesize or fall back to Wikipedia."""
    confidence = state.get("chunk_confidence", 0.0)
    chunks = state.get("retrieved_chunks") or []

    # Use Wikipedia if: low confidence OR no chunks found at all
    if not chunks or confidence < CONFIDENCE_THRESHOLD:
        print(f"[EDGE:confidence] {confidence:.3f} < {CONFIDENCE_THRESHOLD} -> insufficient -> Wikipedia")
        return "insufficient"

    print(f"[EDGE:confidence] {confidence:.3f} >= {CONFIDENCE_THRESHOLD} -> sufficient -> synthesis")
    return "sufficient"
