from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.models import (
    AssessmentReport,
    Course,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    PracticeAnswer,
    PracticeSession,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.reports import ReportEnvelope, empty_report, report_to_api
from backend.app.schemas.personalization import PersonalizationFreshnessResponse
from backend.app.services.learner_context import context_service_from_repository


class ReportNotFoundError(Exception):
    pass


class ReportModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


class ReportRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None: ...

    def get_latest_completed_practice_session(self, user_id: int, course_id: int) -> PracticeSession | None: ...

    def list_recent_completed_practice_sessions(self, user_id: int, course_id: int, limit: int = 5) -> list[PracticeSession]: ...

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None: ...

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def add_assessment_report(self, report: AssessmentReport) -> AssessmentReport: ...

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None:
        return self.db.scalar(select(PracticeSession).where(PracticeSession.id == session_id, PracticeSession.user_id == user_id))

    def get_latest_completed_practice_session(self, user_id: int, course_id: int) -> PracticeSession | None:
        return self.db.scalar(
            select(PracticeSession)
            .where(
                PracticeSession.user_id == user_id,
                PracticeSession.course_id == course_id,
                PracticeSession.status == "completed",
            )
            .order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc())
        )

    def list_recent_completed_practice_sessions(self, user_id: int, course_id: int, limit: int = 5) -> list[PracticeSession]:
        return list(
            self.db.scalars(
                select(PracticeSession)
                .where(
                    PracticeSession.user_id == user_id,
                    PracticeSession.course_id == course_id,
                    PracticeSession.status == "completed",
                )
                .order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc())
                .limit(limit)
            )
        )

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]:
        return list(self.db.scalars(select(PracticeAnswer).where(PracticeAnswer.session_id == session_id).order_by(PracticeAnswer.id)))

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(select(WeaknessReviewItem).where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id))
        )

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath)
            .where(LearningPath.user_id == user_id, LearningPath.course_id == course_id, LearningPath.status == "active")
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return list(self.db.scalars(select(LearningTask).where(LearningTask.path_id == path_id).order_by(LearningTask.id)))

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id, GeneratedResource.course_id == course_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
            )
        )

    def add_assessment_report(self, report: AssessmentReport) -> AssessmentReport:
        self.db.add(report)
        self.db.flush()
        return report

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None:
        return self.db.scalar(
            select(AssessmentReport)
            .where(AssessmentReport.user_id == user_id, AssessmentReport.course_id == course_id)
            .order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


class ReportService:
    def __init__(
        self,
        repository: ReportRepository,
        model_service: ReportModelService | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
    ) -> None:
        self.repository = repository
        self.model_service = model_service
        self.trace_recorder = trace_recorder

    def generate_report(self, user: User, course_id: int, practice_session_id: int | None = None) -> ReportEnvelope:
        from backend.app.agents.reporting import ReportGraphRunner

        return ReportGraphRunner(self).run(user=user, course_id=course_id, practice_session_id=practice_session_id)

    def get_latest_report(self, user: User, course_id: int) -> ReportEnvelope:
        course = self._require_course(user, course_id)
        report = self.repository.get_latest_report(user.id, course.id)
        if report is None:
            return empty_report(course.id)
        return report_to_api(report, self._report_freshness(user.id, report))

    def _report_freshness(
        self,
        user_id: int,
        report: AssessmentReport,
    ) -> PersonalizationFreshnessResponse | None:
        context_service = context_service_from_repository(self.repository)
        if context_service is None:
            return None
        freshness = context_service.freshness(
            report.report_json or {},
            context_service.global_context(user_id).profile_applied_version,
        )
        return PersonalizationFreshnessResponse(**freshness.to_dict())

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise ReportNotFoundError("课程不存在或无权访问。")
        return course

    @staticmethod
    def _score_from_answers(answers: list[PracticeAnswer]) -> int | None:
        scored = [
            int((answer.feedback_json or {})["score"])
            for answer in answers
            if answer.answer_text is not None and (answer.feedback_json or {}).get("score") is not None
        ]
        if not scored:
            return None
        return round(sum(scored) / len(scored))

    def _build_report(
        self,
        course: Course,
        points: list[KnowledgePoint],
        weaknesses: list[WeaknessReviewItem],
        answers: list[PracticeAnswer],
        score: int | None,
    ) -> dict:
        answered = [answer for answer in answers if answer.answer_text is not None]
        graded_answers = [answer for answer in answered if (answer.feedback_json or {}).get("score") is not None]
        wrong_answers = [answer for answer in graded_answers if answer.is_correct is False or int((answer.feedback_json or {})["score"]) < 60]
        weak_point_ids = {
            int((answer.question_json or {}).get("knowledge_point_id"))
            for answer in wrong_answers
            if str((answer.question_json or {}).get("knowledge_point_id") or "").isdigit()
        }
        weakness_rows = [
            {
                "knowledge_point_id": str(point_id),
                "title": self._point_title(points, point_id),
                "source_type": "practice_assessment",
            }
            for point_id in sorted(weak_point_ids)
        ]
        active_weaknesses = [item for item in weaknesses if item.status in {"confirmed", "reviewing"}]
        suggestions = [
            f"优先复习《{course.title}》中得分较低的知识点。",
            "回到课程空间查看引用，再完成下一轮练习。",
        ]
        if active_weaknesses:
            suggestions.insert(0, f"先处理 {len(active_weaknesses)} 个已确认薄弱点。")
        return {
            "summary": f"本次评估得分 {score if score is not None else '暂无'}，基于真实练习作答生成。",
            "mastery_update": {
                "weak_count": len(weakness_rows),
                "mastered_count": sum(1 for answer in answered if answer.is_correct is True),
                "learning_count": max(len(points) - len(weakness_rows), 0),
            },
            "weakness_list": weakness_rows,
            "profile_changes": [],
            "evidence_refs": [
                {
                    "practice_answer_id": str(answer.id),
                    "knowledge_point_id": str((answer.question_json or {}).get("knowledge_point_id") or ""),
                    "score": int((answer.feedback_json or {}).get("score") or 0),
                }
                for answer in graded_answers
            ],
            "next_step_suggestions": suggestions,
            "review_queue_updates": [
                {
                    "title": item.title,
                    "status": item.status,
                    "source_type": item.source_type,
                }
                for item in active_weaknesses[:5]
            ],
        }

    @staticmethod
    def _point_title(points: list[KnowledgePoint], point_id: int) -> str:
        return next((point.title for point in points if point.id == point_id), "练习薄弱点")
