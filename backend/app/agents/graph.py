from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.agents.schemas import AgentState


AGENT_GRAPH_NODE_NAMES = ["profile", "retrieve", "diagnosis", "resource", "review", "persist"]


def create_agent_state(
    *,
    trace_id: str,
    user_id: int,
    course_id: int | None = None,
    knowledge_point_id: int | None = None,
    intent: str = "",
) -> AgentState:
    return {
        "trace_id": trace_id,
        "user_id": user_id,
        "course_id": course_id,
        "knowledge_point_id": knowledge_point_id,
        "intent": intent,
        "profile": {},
        "retrieved_chunks": [],
        "diagnosis": {},
        "generated_resources": [],
        "review_result": {},
        "errors": [],
    }


def _pass_through_node(_state: AgentState) -> dict[str, Any]:
    return {}


def build_agent_graph():
    graph = StateGraph(AgentState)
    for node_name in AGENT_GRAPH_NODE_NAMES:
        graph.add_node(node_name, _pass_through_node)

    graph.add_edge(START, "profile")
    graph.add_edge("profile", "retrieve")
    graph.add_edge("retrieve", "diagnosis")
    graph.add_edge("diagnosis", "resource")
    graph.add_edge("resource", "review")
    graph.add_edge("review", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
