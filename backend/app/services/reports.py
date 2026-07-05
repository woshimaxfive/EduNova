from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AssessmentReport, Course, KnowledgePoint, PracticeAnswer, PracticeSession, User, WeaknessReviewItem
from backend.app.schemas.reports import ReportEnvelope, empty_report, report_to_api


class ReportNotFoundError(Exception):
    pass


class ReportRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None: ...

    def get_latest_completed_practice_session(self, user_id: int, course_id: int) -> PracticeSession | None: ...

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

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

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]:
        return list(self.db.scalars(select(PracticeAnswer).where(PracticeAnswer.session_id == session_id).order_by(PracticeAnswer.id)))

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(select(WeaknessReviewItem).where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id))
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
    def __init__(self, repository: ReportRepository) -> None:
        self.repository = repository

    def generate_report(self, user: User, course_id: int, practice_session_id: int | None = None) -> ReportEnvelope:
        course = self._require_course(user, course_id)
        practice = None
        answers: list[PracticeAnswer] = []
        if practice_session_id is not None:
            practice = self.repository.get_practice_session_for_user(user.id, practice_session_id)
            if practice is None or practice.course_id != course.id:
                raise ReportNotFoundError("练习不存在或无权访问。")
            answers = self.repository.list_answers_for_session(practice.id)
        else:
            practice = self.repository.get_latest_completed_practice_session(user.id, course.id)
            if practice is not None:
                answers = self.repository.list_answers_for_session(practice.id)
            elif self.repository.get_latest_report(user.id, course.id) is not None:
                return report_to_api(self.repository.get_latest_report(user.id, course.id))  # type: ignore[arg-type]

        points = self.repository.list_knowledge_points(course.id)
        weaknesses = self.repository.list_weakness_review_items(user.id, course.id)
        score = int(practice.score) if practice is not None and practice.score is not None else self._score_from_answers(answers)
        report_json = self._build_report(course, points, weaknesses, answers, score)
        report = AssessmentReport(
            user_id=user.id,
            course_id=course.id,
            practice_session_id=practice.id if practice is not None else None,
            report_json=report_json,
            score=Decimal(str(score)) if score is not None else None,
            created_at=datetime.now(UTC),
        )
        try:
            self.repository.add_assessment_report(report)
            self.repository.commit()
            self.repository.refresh(report)
        except Exception:
            self.repository.rollback()
            raise
        return report_to_api(report)

    def get_latest_report(self, user: User, course_id: int) -> ReportEnvelope:
        course = self._require_course(user, course_id)
        report = self.repository.get_latest_report(user.id, course.id)
        if report is None:
            return empty_report(course.id)
        return report_to_api(report)

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise ReportNotFoundError("课程不存在或无权访问。")
        return course

    @staticmethod
    def _score_from_answers(answers: list[PracticeAnswer]) -> int | None:
        scored = [int((answer.feedback_json or {}).get("score") or 0) for answer in answers if answer.answer_text is not None]
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
        wrong_answers = [answer for answer in answered if answer.is_correct is False or int((answer.feedback_json or {}).get("score") or 0) < 60]
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
            "profile_changes": ["练习结果可作为后续画像证据，但本阶段不自动改写用户长期画像。"],
            "evidence_refs": [
                {
                    "practice_answer_id": str(answer.id),
                    "knowledge_point_id": str((answer.question_json or {}).get("knowledge_point_id") or ""),
                    "score": int((answer.feedback_json or {}).get("score") or 0),
                }
                for answer in answered
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
