"""
LangGraph graph definition for the Study Agent.

Graph topology (after Day 5):
    router
      ├─ rag_query      → rag → [sufficient: synthesis | insufficient: wikipedia → synthesis]
      ├─ content_generation → planner → [flashcard_generator | revision_sheet | rag] → synthesis
      ├─ study_planning → gap_analysis → study_plan_builder
      │                                  ├─ has_auth → calendar_node* → synthesis
      │                                  └─ no_auth  → synthesis
      ├─ session_end    → synthesis
      └─ chitchat       → synthesis

  * = LangGraph interrupt fires before calendar_node (human-in-the-loop)

Checkpointer: MemorySaver (in-memory; state is keyed by thread_id = session_id)
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    router_node,
    rag_node,
    wikipedia_node,
    planner_node,
    synthesis_node,
    gap_analysis_node,
    study_plan_builder_node,
    calendar_node,
    flashcard_generator_node,
    revision_sheet_node,
    route_by_intent,
    route_by_confidence,
    route_by_content_type,
    route_by_calendar_auth,
)


def build_graph():
    """Build and compile the LangGraph study agent with Day 5 nodes."""
    graph = StateGraph(AgentState)

    # =========================================================================
    # Register all nodes
    # =========================================================================
    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)
    graph.add_node("wikipedia", wikipedia_node)
    graph.add_node("planner", planner_node)
    graph.add_node("synthesis", synthesis_node)

    # Day 5 nodes
    graph.add_node("gap_analysis", gap_analysis_node)
    graph.add_node("study_plan_builder", study_plan_builder_node)
    graph.add_node("calendar_node", calendar_node)
    graph.add_node("flashcard_generator", flashcard_generator_node)
    graph.add_node("revision_sheet", revision_sheet_node)

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
            "gap_analysis": "gap_analysis",   # study_planning intent
            "synthesis": "synthesis",          # chitchat + session_end
        },
    )

    # =========================================================================
    # RAG pipeline
    # =========================================================================
    graph.add_conditional_edges(
        "rag",
        route_by_confidence,
        {
            "sufficient": "synthesis",
            "insufficient": "wikipedia",
        },
    )
    graph.add_edge("wikipedia", "synthesis")

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
            "rag": "rag",   # generic content gen → retrieve then synthesize
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
    graph.add_edge("calendar_node", "synthesis")

    # =========================================================================
    # Terminal edge — all paths end at synthesis
    # =========================================================================
    graph.add_edge("synthesis", END)

    # =========================================================================
    # Compile with:
    #   - MemorySaver checkpointer (required for interrupt to work)
    #   - interrupt_before=["calendar_node"] (human-in-the-loop)
    # =========================================================================
    checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["calendar_node"],
    )


# Compiled app — import this everywhere you need the agent
study_agent = build_graph()
