from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentRunLog, ModelCallRun, User
from backend.app.schemas.agents import AgentTraceResponse, agent_log_to_api
from backend.app.providers.model_usage import summarize_attempts


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
        model_calls = self.repository.list_model_calls(user.id, trace_id)
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
        total_duration = sum(int(log.duration_ms or 0) for log in logs)
        summary = {
            "model_calls": [
                {
                    "operation": call.operation, "purpose": call.purpose,
                    "model": call.model_name, "provider_source": call.provider_source,
                    "model_config_id": str(call.model_config_id) if call.model_config_id else None,
                    "session_id": str(call.session_id) if call.session_id else None,
                    "status": call.status, "attempt_count": call.attempt_count,
                    "retry_count": call.retry_count, "latency_ms": call.latency_ms,
                    "usage": call.usage_json,
                } for call in model_calls
            ],
            "model_usage": summarize_attempts([
                attempt for call in model_calls
                for attempt in (call.usage_json.get("attempts", []) if call.usage_json is not None else [
                    {"usage_status": "unknown"} for _ in range(max(1, call.attempt_count or 1))
                ])
            ]),
            "duration_ms": total_duration,
            "course_source_count": int(self._last_metadata_value(logs, "course_citation_count") or 0),
            "web_source_count": int(self._last_metadata_value(logs, "web_citation_count") or 0),
            "history_source_count": int(self._last_metadata_value(logs, "context_message_count") or 0),
            "reasoning_mode": self._last_metadata_value(logs, "reasoning_mode") or "auto",
            "search_backend": self._last_metadata_value(logs, "search_backend") or "none",
            "review_status": self._last_metadata_value(logs, "review_status"),
            "safety_summary": self._last_metadata_value(logs, "safety_summary"),
            "personalization_factors": self._last_metadata_value(logs, "personalization_factors") or [],
        }
        return AgentTraceResponse(
            trace_id=trace_id,
            workflow=str(workflow) if workflow is not None else None,
            artifact_type=str(artifact_type) if artifact_type is not None else None,
            artifact_id=str(artifact_id) if artifact_id is not None else None,
            course_id=str(course_id) if course_id is not None else None,
            status=self._derive_trace_status(logs),
            steps=steps,
            summary=summary,
        )

    @staticmethod
    def _first_metadata_value(logs: list[AgentRunLog], key: str) -> object | None:
        for log in logs:
            metadata = log.metadata_json or {}
            if key in metadata and metadata[key] is not None and metadata[key] != "":
                return metadata[key]
        return None

    @staticmethod
    def _last_metadata_value(logs: list[AgentRunLog], key: str) -> object | None:
        for log in reversed(logs):
            metadata = log.metadata_json or {}
            if key in metadata and metadata[key] is not None and metadata[key] != "":
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
