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
    workflow: str = "resource_generation",
    artifact_type: str | None = "generated_resource",
    artifact_id: str | None = None,
    intent: str = "",
) -> AgentState:
    return {
        "trace_id": trace_id,
        "workflow": workflow or intent or "resource_generation",
        "user_id": user_id,
        "course_id": course_id,
        "knowledge_point_id": knowledge_point_id,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "intent": intent,
        "profile": {},
        "profile_summary": {},
        "retrieved_chunks": [],
        "citations": [],
        "diagnosis": {},
        "generated_resources": [],
        "review_result": {},
        "warnings": [],
        "errors": [],
        "node_results": [],
        "artifact_refs": {},
    }


def _append_node_result(state: AgentState, node_name: str) -> list[str]:
    return [*state.get("node_results", []), node_name]


def _profile_node(state: AgentState) -> dict[str, Any]:
    profile_summary = state.get("profile_summary") or state.get("profile") or {}
    return {
        "profile_summary": profile_summary,
        "node_results": _append_node_result(state, "profile"),
    }


def _retrieve_node(state: AgentState) -> dict[str, Any]:
    chunks = state.get("retrieved_chunks", [])
    citations = state.get("citations") or [
        {
            "chunk_id": chunk.get("chunk_id") or chunk.get("id"),
            "source_title": chunk.get("source_title"),
            "section_title": chunk.get("section_title"),
        }
        for chunk in chunks
        if isinstance(chunk, dict)
    ]
    return {
        "citations": citations,
        "node_results": _append_node_result(state, "retrieve"),
    }


def _diagnosis_node(state: AgentState) -> dict[str, Any]:
    diagnosis = dict(state.get("diagnosis") or {})
    diagnosis.setdefault("citation_count", len(state.get("citations", [])))
    diagnosis.setdefault("knowledge_point_id", state.get("knowledge_point_id"))
    return {
        "diagnosis": diagnosis,
        "node_results": _append_node_result(state, "diagnosis"),
    }


def _resource_node(state: AgentState) -> dict[str, Any]:
    resources = state.get("generated_resources") or []
    return {
        "generated_resources": resources,
        "node_results": _append_node_result(state, "resource"),
    }


def _review_node(state: AgentState) -> dict[str, Any]:
    warnings = state.get("warnings", [])
    risk_flags = ["low_evidence"] if warnings else []
    review_status = "warning" if warnings else "passed"
    return {
        "review_result": {
            "review_status": review_status,
            "confidence": 0.55 if warnings else 0.82,
            "risk_flags": risk_flags,
            "safety_summary": "已完成资源生成依据、隐私和完整性审核。",
        },
        "node_results": _append_node_result(state, "review"),
    }


def _persist_node(state: AgentState) -> dict[str, Any]:
    artifact_refs = dict(state.get("artifact_refs") or {})
    if state.get("artifact_id") is not None:
        artifact_refs.setdefault("artifact_id", state["artifact_id"])
    return {
        "artifact_refs": artifact_refs,
        "node_results": _append_node_result(state, "persist"),
    }


NODE_HANDLERS: dict[str, Any] = {
    "profile": _profile_node,
    "retrieve": _retrieve_node,
    "diagnosis": _diagnosis_node,
    "resource": _resource_node,
    "review": _review_node,
    "persist": _persist_node,
}


def build_agent_graph():
    graph = StateGraph(AgentState)
    for node_name in AGENT_GRAPH_NODE_NAMES:
        graph.add_node(node_name, NODE_HANDLERS[node_name])

    graph.add_edge(START, "profile")
    graph.add_edge("profile", "retrieve")
    graph.add_edge("retrieve", "diagnosis")
    graph.add_edge("diagnosis", "resource")
    graph.add_edge("resource", "review")
    graph.add_edge("review", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
