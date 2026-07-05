from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import AgentRunLog, User
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeAgentTraceRepository:
    logs: list[AgentRunLog] = field(default_factory=list)

    def list_trace_logs(self, user_id: int, trace_id: str) -> list[AgentRunLog]:
        return sorted(
            [log for log in self.logs if log.user_id == user_id and log.trace_id == trace_id],
            key=lambda log: (log.step_index, log.created_at, log.id or 0),
        )


def make_user(user_id: int, display_name: str = "Agent 学生") -> User:
    return User(
        id=user_id,
        email=f"agent{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode="blank",
    )


def make_log(
    log_id: int,
    user_id: int,
    trace_id: str,
    agent_name: str,
    step_index: int,
    *,
    course_id: int | None = 808,
    status: str = "completed",
    input_summary: str | None = "读取安全输入摘要",
    output_summary: str | None = "输出安全结果摘要",
    duration_ms: int | None = 12,
    metadata_json: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> AgentRunLog:
    return AgentRunLog(
        id=log_id,
        user_id=user_id,
        course_id=course_id,
        trace_id=trace_id,
        agent_name=agent_name,
        step_index=step_index,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        duration_ms=duration_ms,
        metadata_json=metadata_json or {},
        created_at=created_at or NOW + timedelta(seconds=step_index),
    )


def make_client(user: User, repo: FakeAgentTraceRepository) -> tuple[TestClient, dict[str, str]]:
    from backend.app.api.v1.agents import get_agent_trace_service
    from backend.app.services.agents import AgentTraceService

    settings = Settings(_env_file=None, jwt_secret="agents-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_agent_trace_service] = lambda: AgentTraceService(repo)
    token = create_access_token(str(user.id), settings=settings)
    return TestClient(app), {"Authorization": f"Bearer {token}"}


def test_agent_trace_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/agents/traces/trace_demo")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_agent_trace_route_returns_ordered_steps_for_current_user() -> None:
    user = make_user(1)
    repo = FakeAgentTraceRepository(
        logs=[
            make_log(12, 1, "trace_agent", "review", 3, duration_ms=18),
            make_log(
                10,
                1,
                "trace_agent",
                "retrieve",
                1,
                input_summary="检索课程知识点",
                output_summary="命中 2 条引用",
                duration_ms=25,
                metadata_json={"citation_count": 2, "review_result": "pass", "raw_prompt": "不应返回"},
            ),
            make_log(11, 1, "trace_agent", "diagnosis", 2, status="completed"),
        ]
    )
    client, headers = make_client(user, repo)

    response = client.get("/api/v1/agents/traces/trace_agent", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["trace_id"] == "trace_agent"
    assert data["course_id"] == "808"
    assert data["status"] == "completed"
    assert [step["agent_name"] for step in data["steps"]] == ["retrieve", "diagnosis", "review"]
    assert data["steps"][0] == {
        "id": "10",
        "agent_name": "retrieve",
        "step_index": 1,
        "status": "completed",
        "input_summary": "检索课程知识点",
        "output_summary": "命中 2 条引用",
        "duration_ms": 25,
        "metadata": {"citation_count": 2, "review_result": "pass"},
        "created_at": "2026-07-05T10:00:01Z",
    }


def test_agent_trace_route_hides_missing_and_other_user_traces() -> None:
    user = make_user(1)
    repo = FakeAgentTraceRepository(
        logs=[
            make_log(10, 2, "trace_other_user", "retrieve", 1),
            make_log(11, 1, "trace_visible", "retrieve", 1),
        ]
    )
    client, headers = make_client(user, repo)

    missing_response = client.get("/api/v1/agents/traces/trace_missing", headers=headers)
    other_user_response = client.get("/api/v1/agents/traces/trace_other_user", headers=headers)

    assert missing_response.status_code == 404
    assert other_user_response.status_code == 404


def test_agent_trace_response_does_not_expose_private_prompts_or_source_text() -> None:
    user = make_user(1)
    repo = FakeAgentTraceRepository(
        logs=[
            make_log(
                10,
                1,
                "trace_private",
                "resource",
                1,
                input_summary="系统提示词：请完整读取用户资料原文",
                output_summary="模型输入：这里是完整资料原文",
                metadata_json={
                    "citation_count": 1,
                    "system_prompt": "系统提示词原文",
                    "model_input": "模型输入原文",
                    "raw_source_text": "用户上传资料原文",
                    "api_key": "sk-real-secret",
                },
            )
        ]
    )
    client, headers = make_client(user, repo)

    response = client.get("/api/v1/agents/traces/trace_private", headers=headers)

    assert response.status_code == 200
    serialized = json.dumps(response.json()["data"], ensure_ascii=False)
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "资料原文" not in serialized
    assert "sk-real-secret" not in serialized
    assert response.json()["data"]["steps"][0]["metadata"] == {"citation_count": 1}


def test_agent_graph_builds_stable_phase_8_1_node_sequence() -> None:
    try:
        from backend.app.agents.graph import AGENT_GRAPH_NODE_NAMES, build_agent_graph, create_agent_state
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 Agent graph 模块: {exc.name}")

    state = create_agent_state(
        trace_id="trace_graph",
        user_id=1,
        course_id=808,
        knowledge_point_id=401,
        intent="resource_generation",
    )
    graph = build_agent_graph()
    result = graph.invoke(state)

    assert AGENT_GRAPH_NODE_NAMES == ["profile", "retrieve", "diagnosis", "resource", "review", "persist"]
    assert result["trace_id"] == "trace_graph"
    assert result["user_id"] == 1
    assert result["course_id"] == 808
    assert result["knowledge_point_id"] == 401
    assert result["intent"] == "resource_generation"
    assert result["errors"] == []
