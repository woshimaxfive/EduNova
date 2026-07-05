from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentRunLog, User
from backend.app.schemas.agents import AgentTraceResponse, agent_log_to_api


class AgentTraceNotFoundError(Exception):
    pass


class AgentTraceRepository(Protocol):
    def list_trace_logs(self, user_id: int, trace_id: str) -> list[AgentRunLog]: ...


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


class AgentTraceService:
    def __init__(self, repository: AgentTraceRepository) -> None:
        self.repository = repository

    def get_trace(self, user: User, trace_id: str) -> AgentTraceResponse:
        logs = self.repository.list_trace_logs(user.id, trace_id)
        if not logs:
            raise AgentTraceNotFoundError

        steps = [agent_log_to_api(log) for log in logs]
        course_id = next((log.course_id for log in logs if log.course_id is not None), None)
        return AgentTraceResponse(
            trace_id=trace_id,
            course_id=str(course_id) if course_id is not None else None,
            status=self._derive_trace_status(logs),
            steps=steps,
        )

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
