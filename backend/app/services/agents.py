from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentRunLog, ModelCallRun, User
from backend.app.schemas.agents import AgentTraceResponse, agent_log_to_api


class AgentTraceNotFoundError(Exception):
    pass


class AgentTraceRepository(Protocol):
    def list_trace_logs(self, user_id: int, trace_id: str) -> list[AgentRunLog]: ...
    def list_model_calls(self, user_id: int, trace_id: str) -> list[ModelCallRun]: ...


class SqlAlchemyAgentTraceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_trace_logs(self, user_id: int, trace_id: str) -> list[AgentRunLog]:
        return list(
            self.db.scalars(
                select(AgentRunLog)
                .where(
                    AgentRunLog.user_id == user_id,
                    AgentRunLog.trace_id == trace_id,
                )
                .order_by(AgentRunLog.step_index, AgentRunLog.created_at, AgentRunLog.id)
            )
        )

    def list_model_calls(self, user_id: int, trace_id: str) -> list[ModelCallRun]:
        return list(
            self.db.scalars(
                select(ModelCallRun)
                .where(ModelCallRun.user_id == user_id, ModelCallRun.trace_id == trace_id)
                .order_by(ModelCallRun.started_at, ModelCallRun.id)
            )
        )


class AgentTraceService:
    def __init__(self, repository: AgentTraceRepository) -> None:
        self.repository = repository

    def get_trace(self, user: User, trace_id: str) -> AgentTraceResponse:
        logs = self.repository.list_trace_logs(user.id, trace_id)
        if not logs:
            raise AgentTraceNotFoundError

        steps = [agent_log_to_api(log) for log in logs]
        list_model_calls = getattr(self.repository, "list_model_calls", None)
        model_calls = list_model_calls(user.id, trace_id) if callable(list_model_calls) else []
        if steps and model_calls:
            failed = [item for item in model_calls if item.status != "completed"]
            error_categories = list(dict.fromkeys(item.error_category for item in failed if item.error_category))
            steps[-1].metadata.update(
                {
                    "model_call_count": len(model_calls),
                    "model_retry_count": sum(int(item.retry_count or 0) for item in model_calls),
                    "model_latency_ms": sum(int(item.latency_ms or 0) for item in model_calls),
                    "model_outcome": "degraded" if failed else "completed",
                    "model_error_category": error_categories[0] if error_categories else None,
                }
            )
        course_id = next((log.course_id for log in logs if log.course_id is not None), None)
        workflow = self._first_metadata_value(logs, "workflow")
        artifact_type = self._first_metadata_value(logs, "artifact_type")
        artifact_id = self._first_metadata_value(logs, "artifact_id")
        return AgentTraceResponse(
            trace_id=trace_id,
            workflow=str(workflow) if workflow is not None else None,
            artifact_type=str(artifact_type) if artifact_type is not None else None,
            artifact_id=str(artifact_id) if artifact_id is not None else None,
            course_id=str(course_id) if course_id is not None else None,
            status=self._derive_trace_status(logs),
            steps=steps,
        )

    @staticmethod
    def _first_metadata_value(logs: list[AgentRunLog], key: str) -> object | None:
        for log in logs:
            metadata = log.metadata_json or {}
            if key in metadata and metadata[key] not in {"", None}:
                return metadata[key]
        return None

    @staticmethod
    def _derive_trace_status(logs: list[AgentRunLog]) -> str:
        statuses = {log.status for log in logs}
        if {"failed", "error"} & statuses:
            return "failed"
        if {"queued", "pending", "running"} & statuses:
            return "running"
        if "warning" in statuses:
            return "warning"
        return "completed"
