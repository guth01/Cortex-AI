"""
AgentState — the central data structure flowing through the LangGraph.

Every node reads from and writes to this state.
LangGraph merges state updates automatically between node calls.
"""

from typing import TypedDict, Optional


class AgentState(TypedDict):
    # Core identifiers
    messages: list           # Full conversation history [{role, content}]
    session_id: str          # Active ChromaDB + Atlas session
    user_id: str             # Owner of the session
    subject_id: str          # Subject being studied

    # Routing
    intent: str              # rag_query | content_generation | study_planning | session_end | chitchat

    # RAG pipeline
    retrieved_chunks: list   # Raw chunks from ChromaDB [{content, metadata, score}]
    chunk_confidence: float  # Average similarity score of top-3 results (0.0–1.0)

    # Tool outputs
    tool_results: dict       # Keyed by tool name: {"wikipedia": "...", "gap_analysis": {...}}

    # Planning (for content_generation / study_planning intents)
    plan: list               # Ordered list of steps the planner chose

    # Final output
    response: str            # The final answer text assembled by SynthesisNode

    # Calendar (Day 5 — wired later, kept in state today)
    awaiting_confirmation: bool
    proposed_calendar_events: list
