"""
LangGraph graph definition for the Study Agent.

Graph topology:
    router → [rag | planner | synthesis]
    rag    → [synthesis | wikipedia]  (based on confidence)
    wikipedia → synthesis
    planner   → rag   (planner always runs retrieval after planning)
    synthesis → END
"""

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    router_node,
    rag_node,
    wikipedia_node,
    planner_node,
    synthesis_node,
    route_by_intent,
    route_by_confidence,
)


def build_graph():
    """Build and compile the LangGraph study agent."""
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)
    graph.add_node("wikipedia", wikipedia_node)
    graph.add_node("planner", planner_node)
    graph.add_node("synthesis", synthesis_node)

    # Entry point
    graph.set_entry_point("router")

    # router → branch by intent
    graph.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "rag": "rag",
            "planner": "planner",
            "synthesis": "synthesis",
        },
    )

    # rag → branch by confidence
    graph.add_conditional_edges(
        "rag",
        route_by_confidence,
        {
            "sufficient": "synthesis",
            "insufficient": "wikipedia",
        },
    )

    # Fixed edges
    graph.add_edge("wikipedia", "synthesis")
    graph.add_edge("planner", "rag")   # planner always kicks off retrieval
    graph.add_edge("synthesis", END)

    return graph.compile()


# Compiled app — import this everywhere you need the agent
study_agent = build_graph()
