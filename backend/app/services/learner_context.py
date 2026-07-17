from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.models import (
    AssessmentReport,
    Course,
    CourseEnrollment,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    PracticeAnswer,
    PracticeSession,
    ProfileEvent,
    ResourceInteraction,
    StudentProfile,
    WeaknessReviewItem,
)
from backend.app.schemas.profiles import PROFILE_DIMENSIONS, normalize_profile_json
from backend.app.schemas.personalization import PersonalizationFreshnessResponse
from backend.app.services.resource_feedback import aggregate_resource_interactions
from backend.app.services.mastery_progress import latest_practice_score


@dataclass(frozen=True)
class GlobalLearnerContext:
    profile_values: dict[str, Any] = field(default_factory=dict)
    dimension_confidence: dict[str, float] = field(default_factory=dict)
    trusted_dimensions: tuple[str, ...] = ()
    advisory_dimensions: tuple[str, ...] = ()
    completeness_score: float = 0
    evidence_confidence_score: float = 0
    profile_applied_version: int = 0

    def trusted_value(self, dimension: str, default: Any = "") -> Any:
        return self.profile_values.get(dimension, default) if dimension in self.trusted_dimensions else default

    def advisory_value(self, dimension: str, default: Any = "") -> Any:
        if dimension in self.trusted_dimensions or dimension in self.advisory_dimensions:
            return self.profile_values.get(dimension, default)
        return default

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "profile_applied_version": self.profile_applied_version,
            "profile_completeness": round(self.completeness_score, 2),
            "trusted_dimension_count": len(self.trusted_dimensions),
            "advisory_dimension_count": len(self.advisory_dimensions),
            "profile_context_used": bool(self.trusted_dimensions or self.advisory_dimensions),
        }


@dataclass(frozen=True)
class CourseLearnerContext:
    course_id: int
    course_title: str
    global_context: GlobalLearnerContext
    course_goal: str
    foundation_summary: str
    active_weaknesses: tuple[str, ...]
    mastery_average: int | None
    knowledge_point_count: int
    current_task_title: str | None
    recent_practice_score: int | None
    resource_types: tuple[str, ...]
    resource_feedback_summary: dict[str, dict[str, int]]
    report_ready: bool
    context_hash: str

    def prompt_summary(self) -> dict[str, Any]:
        global_context = self.global_context
        return {
            "course_goal": self.course_goal,
            "foundation_summary": self.foundation_summary,
            "active_weaknesses": list(self.active_weaknesses),
            "learning_goal": self.course_goal,
            "knowledge_foundation": self.foundation_summary,
            "weak_points": list(self.active_weaknesses),
            "profile_weak_points": list(global_context.trusted_value("weak_points", [])),
            "mastery_average": self.mastery_average,
            "current_task_title": self.current_task_title,
            "major_background": global_context.trusted_value("major_background"),
            "learning_preference": global_context.trusted_value("learning_preference"),
            "cognitive_style": global_context.trusted_value("cognitive_style"),
            "learning_pace": global_context.trusted_value("learning_pace"),
            "motivation_interest": global_context.trusted_value("motivation_interest"),
            "resource_feedback": self.resource_feedback_summary,
        }

    def trace_metadata(self) -> dict[str, Any]:
        summary = self.prompt_summary()
        factor_codes = [
            key
            for key in ("major_background", "knowledge_foundation", "learning_goal", "learning_preference", "cognitive_style", "learning_pace", "motivation_interest", "profile_weak_points")
            if summary.get(key)
        ]
        if self.active_weaknesses:
            factor_codes.append("confirmed_weaknesses")
        if self.mastery_average is not None:
            factor_codes.append("course_mastery")
        if self.resource_feedback_summary:
            factor_codes.append("resource_feedback")
        return {
            **self.global_context.trace_metadata(),
            "course_context_hash": self.context_hash,
            "course_weakness_count": len(self.active_weaknesses),
            "mastery_average": self.mastery_average,
            "resource_feedback_type_count": len(self.resource_feedback_summary),
            "personalization_factors": factor_codes,
        }


@dataclass(frozen=True)
class PersonalizationFreshness:
    status: str
    profile_applied_version: int | None
    current_profile_applied_version: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LearnerContextService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def global_context(self, user_id: int) -> GlobalLearnerContext:
        profile = self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))
        if profile is None:
            return GlobalLearnerContext(profile_values=normalize_profile_json(None))
        values = normalize_profile_json(profile.profile_json)
        confidence = {
            key: float(value)
            for key, value in (profile.dimension_confidence_json or {}).items()
            if key in PROFILE_DIMENSIONS and isinstance(value, (int, float))
        }
        completed = sum(1 for key in PROFILE_DIMENSIONS if bool(values.get(key)))
        trusted = tuple(key for key in PROFILE_DIMENSIONS if confidence.get(key, 0) >= 70 and values.get(key))
        advisory = tuple(key for key in PROFILE_DIMENSIONS if 50 <= confidence.get(key, 0) < 70 and values.get(key))
        applied_version = int(
            self.db.scalar(
                select(func.count()).select_from(ProfileEvent).where(
                    ProfileEvent.profile_id == profile.id,
                    ProfileEvent.status == "applied",
                )
            )
            or 0
        )
        evidence_values = [confidence[key] for key in PROFILE_DIMENSIONS if values.get(key) and key in confidence]
        return GlobalLearnerContext(
            profile_values=values,
            dimension_confidence=confidence,
            trusted_dimensions=trusted,
            advisory_dimensions=advisory,
            completeness_score=round(completed / len(PROFILE_DIMENSIONS) * 100, 2),
            evidence_confidence_score=round(sum(evidence_values) / len(evidence_values), 2) if evidence_values else 0,
            profile_applied_version=applied_version,
        )

    def course_context(self, user_id: int, course_id: int) -> CourseLearnerContext:
        course = self.db.scalar(
            select(Course)
            .outerjoin(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(
                Course.id == course_id,
                or_(Course.owner_id == user_id, CourseEnrollment.user_id == user_id),
            )
        )
        if course is None:
            raise ValueError("课程不存在或无权访问。")
        global_context = self.global_context(user_id)
        active_path = self.db.scalar(
            select(LearningPath).where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.status == "active",
            ).order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )
        tasks = list(
            self.db.scalars(
                select(LearningTask).where(
                    LearningTask.user_id == user_id,
                    LearningTask.course_id == course_id,
                    LearningTask.path_id == active_path.id,
                ).order_by(LearningTask.id)
            )
        ) if active_path is not None else []
        current_task = next((task for task in tasks if task.status == "doing"), None)
        if current_task is None:
            current_task = next((task for task in tasks if task.status == "todo"), None)
        weaknesses = list(
            self.db.scalars(
                select(WeaknessReviewItem).where(
                    WeaknessReviewItem.user_id == user_id,
                    WeaknessReviewItem.course_id == course_id,
                    WeaknessReviewItem.status.in_(("confirmed", "reviewing")),
                ).order_by(WeaknessReviewItem.updated_at.desc(), WeaknessReviewItem.id.desc())
            )
        )
        practice_sessions = list(
            self.db.scalars(
                select(PracticeSession).where(
                    PracticeSession.user_id == user_id,
                    PracticeSession.course_id == course_id,
                    PracticeSession.status == "completed",
                ).order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc()).limit(5)
            )
        )
        scores = [int(session.score) for session in practice_sessions if session.score is not None]
        knowledge_points = list(
            self.db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )
        practice_answers = list(
            self.db.scalars(
                select(PracticeAnswer)
                .join(PracticeSession, PracticeSession.id == PracticeAnswer.session_id)
                .where(
                    PracticeAnswer.user_id == user_id,
                    PracticeSession.course_id == course_id,
                    PracticeSession.status == "completed",
                )
            )
        )
        mastery_scores = self._mastery_scores(knowledge_points, weaknesses, practice_answers)
        mastery_average = round(sum(mastery_scores) / len(mastery_scores)) if mastery_scores else None
        knowledge_point_count = len(knowledge_points)
        resource_types = tuple(dict.fromkeys(
            self.db.scalars(
                select(GeneratedResource.resource_type).where(
                    GeneratedResource.user_id == user_id,
                    GeneratedResource.course_id == course_id,
                    GeneratedResource.status == "completed",
                ).order_by(GeneratedResource.updated_at.desc())
            )
        ))
        feedback_rows = list(
            self.db.execute(
                select(
                    ResourceInteraction.resource_id,
                    GeneratedResource.resource_type,
                    ResourceInteraction.event_type,
                    ResourceInteraction.feedback,
                    ResourceInteraction.created_at,
                    ResourceInteraction.id,
                )
                .join(GeneratedResource, GeneratedResource.id == ResourceInteraction.resource_id)
                .where(
                    ResourceInteraction.user_id == user_id,
                    ResourceInteraction.course_id == course_id,
                )
            )
        )
        resource_feedback_summary = aggregate_resource_interactions(feedback_rows)
        report_ready = self.db.scalar(
            select(AssessmentReport.id).where(
                AssessmentReport.user_id == user_id,
                AssessmentReport.course_id == course_id,
            ).order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        ) is not None
        global_goal = str(global_context.trusted_value("learning_goal") or "").strip()
        course_goal = str(active_path.goal or "").strip() if active_path is not None else ""
        course_goal = course_goal or global_goal or f"完成《{course.title}》学习"
        foundation = str(global_context.trusted_value("knowledge_foundation") or "").strip()
        foundation_summary = foundation or "尚未形成可信基础判断"
        if knowledge_point_count and mastery_average is not None:
            foundation_summary = f"{foundation_summary}；当前课程掌握度约 {mastery_average}%"
        payload = {
            "course_id": course_id,
            "profile_applied_version": global_context.profile_applied_version,
            "course_goal": course_goal,
            "foundation_summary": foundation_summary,
            "active_weaknesses": [item.title for item in weaknesses],
            "mastery_average": mastery_average,
            "current_task": current_task.title if current_task is not None else None,
            "resource_types": list(resource_types),
            "resource_feedback": resource_feedback_summary,
            "report_ready": report_ready,
        }
        context_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return CourseLearnerContext(
            course_id=course_id,
            course_title=course.title,
            global_context=global_context,
            course_goal=course_goal,
            foundation_summary=foundation_summary,
            active_weaknesses=tuple(item.title for item in weaknesses),
            mastery_average=mastery_average,
            knowledge_point_count=knowledge_point_count,
            current_task_title=current_task.title if current_task is not None else None,
            recent_practice_score=scores[0] if scores else None,
            resource_types=resource_types,
            resource_feedback_summary=resource_feedback_summary,
            report_ready=report_ready,
            context_hash=context_hash,
        )

    @staticmethod
    def _mastery_scores(
        knowledge_points: list[KnowledgePoint],
        weaknesses: list[WeaknessReviewItem],
        answers: list[PracticeAnswer],
    ) -> list[int]:
        weakness_ids = {
            item.knowledge_point_id
            for item in weaknesses
            if item.knowledge_point_id is not None and item.status in {"confirmed", "reviewing"}
        }
        answers_by_point: dict[int, list[PracticeAnswer]] = {}
        for answer in answers:
            raw_point_id = (answer.question_json or {}).get("knowledge_point_id")
            if str(raw_point_id or "").isdigit():
                answers_by_point.setdefault(int(raw_point_id), []).append(answer)
        result: list[int] = []
        for point in knowledge_points:
            point_answers = answers_by_point.get(point.id, [])
            current_score = latest_practice_score(point_answers)
            if current_score is not None:
                result.append(current_score)
            elif point.id in weakness_ids:
                result.append(35)
        return result

    @staticmethod
    def freshness(metadata: dict[str, Any] | None, current_version: int) -> PersonalizationFreshness:
        raw_version = (metadata or {}).get("profile_applied_version")
        if not isinstance(raw_version, int):
            return PersonalizationFreshness(
                status="legacy",
                profile_applied_version=None,
                current_profile_applied_version=current_version,
                reason="该成果生成于画像版本记录启用之前。",
            )
        if raw_version < current_version:
            return PersonalizationFreshness(
                status="stale",
                profile_applied_version=raw_version,
                current_profile_applied_version=current_version,
                reason="学习画像已变化，可更新该成果以应用新的个性化依据。",
            )
        return PersonalizationFreshness(
            status="current",
            profile_applied_version=raw_version,
            current_profile_applied_version=current_version,
            reason="该成果已使用当前学习画像。",
        )

    def freshness_response(self, metadata: dict[str, Any] | None, user_id: int) -> PersonalizationFreshnessResponse:
        result = self.freshness(metadata, self.global_context(user_id).profile_applied_version)
        return PersonalizationFreshnessResponse(**result.to_dict())


def context_service_from_repository(repository: Any) -> LearnerContextService | None:
    db = getattr(repository, "db", None)
    return LearnerContextService(db) if isinstance(db, Session) else None
