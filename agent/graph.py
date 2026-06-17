"""
LangGraph graph definition for the Study Agent.

Graph topology (after Sufficiency Judge redesign):

    router
      ├─ rag_query      → rag → sufficiency_judge
      │                         ├─ SUFFICIENT  → synthesis
      │                         └─ PARTIAL/INSUFFICIENT → await_fallback [INTERRUPT]
      │                                           ├─ gemini  → synthesis
      │                                           └─ tavily  → tavily_search → synthesis
      │
      ├─ content_generation → planner → [flashcard_generator | revision_sheet | rag] → synthesis
      ├─ study_planning     → gap_analysis → study_plan_builder
      │                                      ├─ has_auth → calendar_node* → synthesis
      │                                      └─ no_auth  → synthesis
      ├─ calendar_scheduling → direct_calendar_builder
      │                        ├─ has_auth → calendar_node* → synthesis
      │                        └─ no_auth  → synthesis
      ├─ session_end    → synthesis
      └─ chitchat       → synthesis

  * = LangGraph interrupt fires before calendar_node (human-in-the-loop)

Interrupt points:
  - interrupt_before=["await_fallback_node"]  — fires when judge verdict is PARTIAL/INSUFFICIENT
  - interrupt_before=["calendar_node"]         — fires before creating Google Calendar events

Checkpointer: MemorySaver (in-memory; state is keyed by thread_id = session_id)
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    router_node,
    rag_node,
    sufficiency_judge_node,
    await_fallback_node,
    tavily_search_node,
    planner_node,
    synthesis_node,
    gap_analysis_node,
    study_plan_builder_node,
    calendar_node,
    flashcard_generator_node,
    revision_sheet_node,
    direct_calendar_builder_node,
    translation_node,
    evaluator_node,
    summary_node,
    save_node,
    route_by_intent,
    route_after_judge,
    route_after_fallback_choice,
    route_by_content_type,
    route_by_calendar_auth,
)


def build_graph():
    """Build and compile the LangGraph study agent with Sufficiency Judge pipeline."""
    graph = StateGraph(AgentState)

    # =========================================================================
    # Register all nodes
    # =========================================================================
    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)

    # Sufficiency Judge pipeline (replaces Wikipedia fallback)
    graph.add_node("sufficiency_judge", sufficiency_judge_node)
    graph.add_node("await_fallback_node", await_fallback_node)  # interrupt anchor
    graph.add_node("tavily_search", tavily_search_node)

    graph.add_node("planner", planner_node)
    graph.add_node("synthesis", synthesis_node)

    # Day 5 nodes
    graph.add_node("gap_analysis", gap_analysis_node)
    graph.add_node("study_plan_builder", study_plan_builder_node)
    graph.add_node("direct_calendar_builder", direct_calendar_builder_node)
    graph.add_node("calendar_node", calendar_node)
    graph.add_node("flashcard_generator", flashcard_generator_node)
    graph.add_node("revision_sheet", revision_sheet_node)
    graph.add_node("translation", translation_node)

    # Day 7 nodes — session end pipeline
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("summary_node", summary_node)
    graph.add_node("save_node", save_node)

    # =========================================================================
    # Entry point
    # =========================================================================
    graph.set_entry_point("router")

    # =========================================================================
    # router → branch by intent
    # =========================================================================
    graph.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "rag": "rag",
            "planner": "planner",
            "gap_analysis": "gap_analysis",               # study_planning intent
            "direct_calendar_builder": "direct_calendar_builder",  # calendar_scheduling intent
            "translation": "translation",                 # translation intent
            "synthesis": "synthesis",                     # chitchat + session_end
            "evaluator": "evaluator",                     # session_end intent
        },
    )

    # =========================================================================
    # RAG pipeline — Sufficiency Judge replaces route_by_confidence + Wikipedia
    # =========================================================================
    graph.add_edge("rag", "sufficiency_judge")

    graph.add_conditional_edges(
        "sufficiency_judge",
        route_after_judge,
        {
            "synthesis": "synthesis",          # SUFFICIENT — go straight to answer
            "await_fallback": "await_fallback_node",  # PARTIAL/INSUFFICIENT — interrupt
        },
    )

    # After user chooses fallback strategy → route to Tavily or Gemini synthesis
    graph.add_conditional_edges(
        "await_fallback_node",
        route_after_fallback_choice,
        {
            "tavily_search": "tavily_search",  # user chose Tavily
            "synthesis": "synthesis",          # user chose Gemini
        },
    )

    # Tavily results flow directly into synthesis
    graph.add_edge("tavily_search", "synthesis")

    # =========================================================================
    # Content generation pipeline
    # planner → detect content type → [flashcard_generator | revision_sheet | rag]
    # =========================================================================
    graph.add_conditional_edges(
        "planner",
        route_by_content_type,
        {
            "flashcard_generator": "flashcard_generator",
            "revision_sheet": "revision_sheet",
            "rag": "rag",   # generic content gen → retrieve then judge then synthesize
        },
    )
    graph.add_edge("flashcard_generator", "synthesis")
    graph.add_edge("revision_sheet", "synthesis")

    # =========================================================================
    # Study planning pipeline (Day 5)
    # gap_analysis → study_plan_builder → [calendar_node* | synthesis]
    # * interrupt fires before calendar_node
    # =========================================================================
    graph.add_edge("gap_analysis", "study_plan_builder")

    graph.add_conditional_edges(
        "study_plan_builder",
        route_by_calendar_auth,
        {
            "has_auth": "calendar_node",   # interrupt will fire here
            "no_auth": "synthesis",        # just returns plan as text
        },
    )

    graph.add_conditional_edges(
        "direct_calendar_builder",
        route_by_calendar_auth,
        {
            "has_auth": "calendar_node",
            "no_auth": "synthesis",
        },
    )

    graph.add_edge("calendar_node", "synthesis")
    graph.add_edge("translation", "synthesis")

    # =========================================================================
    # Session end pipeline (Day 7) — evaluator → summary_node → save_node → END
    # save_node handles Atlas update + ChromaDB cleanup, then returns response
    # =========================================================================
    graph.add_edge("evaluator", "summary_node")
    graph.add_edge("summary_node", "save_node")
    graph.add_edge("save_node", END)

    # =========================================================================
    # Terminal edge — all other paths end at synthesis
    # =========================================================================
    graph.add_edge("synthesis", END)

    # =========================================================================
    # Compile with:
    #   - MemorySaver checkpointer (required for interrupts to work)
    #   - interrupt_before=["await_fallback_node", "calendar_node"]
    #     await_fallback_node → pauses for user fallback strategy choice
    #     calendar_node       → pauses for user plan confirmation
    # =========================================================================
    checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await_fallback_node", "calendar_node"],
    )


# Compiled app — import this everywhere you need the agent
study_agent = build_graph()
