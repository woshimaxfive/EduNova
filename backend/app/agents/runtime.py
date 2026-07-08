from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models import AgentRunLog
from backend.app.schemas.agents import safe_agent_metadata, safe_agent_summary


TRACE_METADATA_DEFAULTS = {
    "workflow": None,
    "artifact_type": None,
    "artifact_id": None,
}


@dataclass(frozen=True)
class PendingAgentTrace:
    agent_name: str
    step_index: int
    status: str
    input_summary: str
    output_summary: str
    duration_ms: int
    metadata: dict[str, Any]


def build_trace_metadata(
    *,
    workflow: str,
    artifact_type: str | None = None,
    artifact_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = {
        "workflow": workflow,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
    }
    merged.update(metadata or {})
    return {key: value for key, value in merged.items() if value is not None}


def agent_log_from_pending_trace(
    *,
    pending: PendingAgentTrace,
    trace_id: str,
    user_id: int,
    course_id: int | None,
    workflow: str,
    artifact_type: str | None = None,
    artifact_id: str | None = None,
) -> AgentRunLog:
    metadata = build_trace_metadata(
        workflow=workflow,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        metadata=pending.metadata,
    )
    return AgentRunLog(
        user_id=user_id,
        course_id=course_id,
        trace_id=trace_id,
        agent_name=pending.agent_name,
        step_index=pending.step_index,
        status=pending.status,
        input_summary=safe_agent_summary(pending.input_summary, "已隐藏敏感输入摘要"),
        output_summary=safe_agent_summary(pending.output_summary, "已隐藏敏感输出摘要"),
        duration_ms=pending.duration_ms,
        metadata_json=safe_agent_metadata(metadata),
        created_at=datetime.now(UTC),
    )


class AgentTraceRecorder:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        repository_add_log: Callable[[AgentRunLog], Any] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.repository_add_log = repository_add_log

    @contextmanager
    def node(
        self,
        *,
        trace_id: str,
        user_id: int,
        course_id: int | None,
        agent_name: str,
        step_index: int,
        input_summary: str,
        workflow: str,
        artifact_type: str | None = None,
        artifact_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        started = perf_counter()
        try:
            yield
        except Exception as exc:
            duration_ms = int((perf_counter() - started) * 1000)
            self.record(
                trace_id=trace_id,
                user_id=user_id,
                course_id=course_id,
                agent_name=agent_name,
                step_index=step_index,
                status="failed",
                input_summary=input_summary,
                output_summary="节点执行失败，已记录安全错误摘要。",
                duration_ms=duration_ms,
                workflow=workflow,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                metadata={**(metadata or {}), "error_code": exc.__class__.__name__},
            )
            raise

    def record(
        self,
        *,
        trace_id: str,
        user_id: int,
        course_id: int | None,
        agent_name: str,
        step_index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int | None,
        workflow: str,
        artifact_type: str | None = None,
        artifact_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRunLog:
        log = AgentRunLog(
            user_id=user_id,
            course_id=course_id,
            trace_id=trace_id,
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=safe_agent_summary(input_summary, "已隐藏敏感输入摘要"),
            output_summary=safe_agent_summary(output_summary, "已隐藏敏感输出摘要"),
            duration_ms=duration_ms,
            metadata_json=safe_agent_metadata(
                build_trace_metadata(
                    workflow=workflow,
                    artifact_type=artifact_type,
                    artifact_id=artifact_id,
                    metadata=metadata,
                )
            ),
            created_at=datetime.now(UTC),
        )

        if self.repository_add_log is not None:
            return self.repository_add_log(log)

        with self.session_factory() as session:
            session.add(log)
            session.commit()
            session.refresh(log)
            return log
