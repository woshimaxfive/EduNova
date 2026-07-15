from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, START, MessagesState, StateGraph


class SearchService(Protocol):
    def search(self, query: str, max_results: int | None = None) -> Any: ...


def create_search_web_tool(service: SearchService) -> BaseTool:
    @tool("search_web", response_format="content_and_artifact")
    def search_web(query: str, max_results: int = 5) -> tuple[str, dict[str, Any]]:
        """Search the public web for verifiable current sources using only the necessary query."""
        result = service.search(query, max_results=max(1, min(max_results, 8)))
        artifact = {
            "citations": list(getattr(result, "citations", []) or []),
            "warning": getattr(result, "warning", None),
        }
        content = json.dumps(
            {"source_count": len(artifact["citations"]), "warning": artifact["warning"]},
            ensure_ascii=False,
        )
        return content, artifact

    return search_web


class SearchToolExecutor:
    """Execute the approved search tool through ToolNode without handing over graph orchestration."""

    def __init__(self, service: SearchService) -> None:
        self.tool = create_search_web_tool(service)
        self.node = ToolNode([self.tool])
        graph = StateGraph(MessagesState)
        graph.add_node("tools", self.node)
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        self.graph = graph.compile()

    def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        call_id = f"search-{uuid4().hex}"
        output = self.graph.invoke({
            "messages": [AIMessage(content="", tool_calls=[{
                "name": self.tool.name,
                "args": {"query": query, "max_results": max_results},
                "id": call_id,
                "type": "tool_call",
            }])]
        })
        messages = output.get("messages", []) if isinstance(output, dict) else []
        for message in reversed(messages):
            if isinstance(message, ToolMessage) and message.tool_call_id == call_id:
                return dict(message.artifact) if isinstance(message.artifact, dict) else {}
        return {}
