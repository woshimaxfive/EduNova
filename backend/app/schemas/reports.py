from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from backend.app.models import AssessmentReport
from backend.app.schemas.personalization import PersonalizationFreshnessResponse


class GenerateReportRequest(BaseModel):
    course_id: int
    practice_session_id: int | None = None


class ReportEnvelope(BaseModel):
    id: str | None
    course_id: str
    practice_session_id: str | None
    status: str
    agent_trace_id: str | None = None
    score: int | None
    report: dict
    personalization: PersonalizationFreshnessResponse | None = None
    created_at: str | None


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def empty_report(course_id: int) -> ReportEnvelope:
    return ReportEnvelope(
        id=None,
        course_id=str(course_id),
        practice_session_id=None,
        status="empty",
        agent_trace_id=None,
        score=None,
        report={
            "summary": "还没有真实学习报告。",
            "mastery_update": {"weak_count": 0, "mastered_count": 0, "learning_count": 0},
            "weakness_list": [],
            "evidence_refs": [],
            "next_step_suggestions": ["完成一次课程练习后生成报告。"],
            "review_queue_updates": [],
            "profile_changes": [],
        },
        personalization=None,
        created_at=None,
    )


def report_to_api(
    report: AssessmentReport,
    personalization: PersonalizationFreshnessResponse | None = None,
) -> ReportEnvelope:
    return ReportEnvelope(
        id=str(report.id),
        course_id=str(report.course_id),
        practice_session_id=str(report.practice_session_id) if report.practice_session_id is not None else None,
        status="ready",
        agent_trace_id=getattr(report, "agent_trace_id", None),
        score=int(report.score) if report.score is not None else None,
        report=report.report_json or {},
        personalization=personalization,
        created_at=iso_timestamp(report.created_at),
    )
