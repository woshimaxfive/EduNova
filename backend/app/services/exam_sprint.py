from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.models import (
    AssessmentReport,
    Course,
    CourseMaterial,
    CourseMaterialLink,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    Material,
    MaterialComparisonRun,
    PracticeAnswer,
    PracticeSession,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.exam_sprint import (
    ExamSprintDailyTask,
    ExamSprintEvidenceSummary,
    ExamSprintPlanResponse,
    ExamSprintPoint,
    ExamSprintQuestion,
    ExamSprintWarning,
    exam_sprint_resource_brief,
    iso_timestamp,
    path_timestamps,
)


class ExamSprintNotFoundError(Exception):
    pass


class ExamSprintValidationError(Exception):
    pass


class ExamSprintModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


class ExamSprintRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def validate_material_ids(self, user_id: int, course_id: int, material_ids: list[int]) -> bool: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]: ...

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def get_comparison_run_for_user(self, user_id: int, comparison_id: int) -> MaterialComparisonRun | None: ...

    def get_current_sprint_path(self, user_id: int, course_id: int) -> LearningPath | None: ...

    def archive_active_sprint_paths(self, user_id: int, course_id: int) -> None: ...

    def add_path(self, path: LearningPath) -> LearningPath: ...

    def add_task(self, task: LearningTask) -> LearningTask: ...

    def get_sprint_path_for_user(self, user_id: int, plan_id: int) -> LearningPath | None: ...

    def get_sprint_task_for_user(self, user_id: int, plan_id: int, task_id: int) -> LearningTask | None: ...

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyExamSprintRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def validate_material_ids(self, user_id: int, course_id: int, material_ids: list[int]) -> bool:
        if not material_ids:
            return True

        requested = set(material_ids)
        course_material_ids = set(
            self.db.scalars(
                select(CourseMaterial.id).where(
                    CourseMaterial.user_id == user_id,
                    CourseMaterial.course_id == course_id,
                    CourseMaterial.id.in_(requested),
                )
            )
        )
        linked_library_ids = set(
            self.db.scalars(
                select(CourseMaterialLink.material_id)
                .join(Material, Material.id == CourseMaterialLink.material_id)
                .where(
                    Material.user_id == user_id,
                    CourseMaterialLink.course_id == course_id,
                    CourseMaterialLink.material_id.in_(requested),
                )
            )
        )
        return requested.issubset(course_material_ids | linked_library_ids)

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id)
                .order_by(WeaknessReviewItem.updated_at.desc(), WeaknessReviewItem.id.desc())
            )
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id, GeneratedResource.course_id == course_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
            )
        )

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        return list(
            self.db.scalars(
                select(PracticeAnswer)
                .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
                .where(
                    PracticeAnswer.user_id == user_id,
                    PracticeSession.user_id == user_id,
                    PracticeSession.course_id == course_id,
                    PracticeSession.status == "completed",
                )
                .order_by(PracticeAnswer.created_at.desc(), PracticeAnswer.id.desc())
            )
        )

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None:
        return self.db.scalar(
            select(AssessmentReport)
            .where(AssessmentReport.user_id == user_id, AssessmentReport.course_id == course_id)
            .order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        )

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def get_comparison_run_for_user(self, user_id: int, comparison_id: int) -> MaterialComparisonRun | None:
        return self.db.scalar(
            select(MaterialComparisonRun).where(
                MaterialComparisonRun.id == comparison_id,
                MaterialComparisonRun.user_id == user_id,
            )
        )

    def get_current_sprint_path(self, user_id: int, course_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.status == "sprint_active",
            )
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
            .limit(1)
        )

    def archive_active_sprint_paths(self, user_id: int, course_id: int) -> None:
        for path in self.db.scalars(
            select(LearningPath).where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.status == "sprint_active",
            )
        ):
            path.status = "sprint_archived"
            path.updated_at = datetime.now(UTC)

    def add_path(self, path: LearningPath) -> LearningPath:
        self.db.add(path)
        self.db.flush()
        return path

    def add_task(self, task: LearningTask) -> LearningTask:
        self.db.add(task)
        self.db.flush()
        return task

    def get_sprint_path_for_user(self, user_id: int, plan_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath).where(
                LearningPath.id == plan_id,
                LearningPath.user_id == user_id,
                LearningPath.status.in_(["sprint_active", "sprint_archived"]),
            )
        )

    def get_sprint_task_for_user(self, user_id: int, plan_id: int, task_id: int) -> LearningTask | None:
        return self.db.scalar(
            select(LearningTask).where(
                LearningTask.id == task_id,
                LearningTask.path_id == plan_id,
                LearningTask.user_id == user_id,
            )
        )

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.path_id == path_id)
                .order_by(LearningTask.due_at.asc(), LearningTask.id.asc())
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


@dataclass
class SprintPointCandidate:
    knowledge_point_id: int | None
    title: str
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    weak: bool = False


@dataclass(frozen=True)
class SprintTaskSpec:
    day_index: int
    title: str
    task_type: str
    knowledge_point_id: int | None
    reason: str
    resource_ids: list[int]
    due_at: datetime
    status: str


@dataclass(frozen=True)
class ExamSprintReplanResult:
    status: str
    plan_id: int | None
    trace_id: str | None
    detail: ExamSprintPlanResponse | None


class ExamSprintService:
    validation_error = ExamSprintValidationError
    not_found_error = ExamSprintNotFoundError
    valid_durations = {3, 7, 14}

    def __init__(
        self,
        repository: ExamSprintRepository,
        model_service: ExamSprintModelService | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
    ) -> None:
        self.repository = repository
        self.model_service = model_service
        self.trace_recorder = trace_recorder

    def generate_plan(
        self,
        user: User,
        course_id: int,
        duration_days: int,
        material_ids: list[int] | None = None,
        comparison_id: int | None = None,
        goal: str = "",
    ) -> ExamSprintPlanResponse:
        if duration_days not in self.valid_durations:
            raise ExamSprintValidationError("冲刺计划时长只能是 3、7 或 14 天。")
        from backend.app.agents.exam_sprint import ExamSprintGraphRunner

        return ExamSprintGraphRunner(self).run(
            user=user,
            course_id=course_id,
            duration_days=duration_days,
            material_ids=material_ids or [],
            comparison_id=comparison_id,
            goal=goal,
            trigger="manual",
        )

    def get_current_plan(self, user: User, course_id: int) -> ExamSprintPlanResponse | None:
        course = self._require_course(user, course_id)
        path = self.repository.get_current_sprint_path(user.id, course.id)
        if path is None:
            return None
        resources = self.repository.list_generated_resources(user.id, course.id)
        return self._build_response(path, self.repository.list_tasks_for_path(path.id), resources)

    def validate_practice_source(self, user: User, course_id: int, plan_id: int, task_id: int) -> LearningTask:
        path = self.repository.get_sprint_path_for_user(user.id, plan_id)
        if path is None or path.status != "sprint_active" or int(path.course_id or 0) != course_id:
            raise ExamSprintNotFoundError("冲刺计划不存在、已归档或不属于当前课程。")
        task = self.repository.get_sprint_task_for_user(user.id, plan_id, task_id)
        if task is None or int(task.course_id or 0) != course_id or task.task_type != "sprint_practice":
            raise ExamSprintNotFoundError("冲刺必刷题任务不存在或无权访问。")
        return task

    def replan_after_assessment(
        self,
        user: User,
        course_id: int,
        assessment_session_id: int,
        plan_id: int,
        task_id: int,
    ) -> ExamSprintReplanResult:
        previous = self.repository.get_sprint_path_for_user(user.id, plan_id)
        if previous is None or previous.status != "sprint_active" or int(previous.course_id or 0) != course_id:
            return ExamSprintReplanResult("unchanged", None, None, None)
        task = self.validate_practice_source(user, course_id, plan_id, task_id)
        task.status = "completed"
        task.updated_at = datetime.now(UTC)
        # The practice result and its source task are already facts. Persist the
        # completion before starting an independent replanning transaction so a
        # failed graph run cannot reopen the task.
        self.repository.commit()
        self.repository.refresh(task)
        plan_json = previous.plan_json or {}
        duration_days = int(plan_json.get("duration_days") or 7)
        comparison_id = self._safe_int(plan_json.get("comparison_id"))
        material_ids = [self._safe_int(item) for item in plan_json.get("material_ids") or []]
        from backend.app.agents.exam_sprint import ExamSprintGraphRunner

        detail = ExamSprintGraphRunner(self).run(
            user=user,
            course_id=course_id,
            duration_days=duration_days if duration_days in self.valid_durations else 7,
            material_ids=[item for item in material_ids if item is not None],
            comparison_id=comparison_id,
            goal=previous.goal or "",
            trigger="assessment_reflow",
            source_practice_session_id=assessment_session_id,
            previous_path=previous,
        )
        return ExamSprintReplanResult("replanned", int(detail.id), detail.agent_trace_id, detail)

    def get_plan(self, user: User, plan_id: int) -> ExamSprintPlanResponse:
        path = self.repository.get_sprint_path_for_user(user.id, plan_id)
        if path is None:
            raise ExamSprintNotFoundError("冲刺计划不存在或无权访问。")
        resources = self.repository.list_generated_resources(user.id, int(path.course_id or 0))
        return self._build_response(path, self.repository.list_tasks_for_path(path.id), resources)

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise ExamSprintNotFoundError("课程不存在或无权访问。")
        return course

    def _collect_context(self, user: User, course: Course) -> dict:
        get_profile = getattr(self.repository, "get_profile", None)
        return {
            "profile": get_profile(user.id) if callable(get_profile) else None,
            "knowledge_points": self.repository.list_knowledge_points(course.id),
            "weakness_items": self.repository.list_weakness_review_items(user.id, course.id),
            "resources": self.repository.list_generated_resources(user.id, course.id),
            "practice_answers": self.repository.list_practice_answers(user.id, course.id),
            "report": self.repository.get_latest_report(user.id, course.id),
        }

    def _build_plan_payload(
        self,
        course: Course,
        duration_days: int,
        goal: str,
        material_filter_count: int,
        now: datetime,
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
        practice_answers: list[PracticeAnswer],
        report: AssessmentReport | None,
    ) -> dict:
        point_candidates = self._score_points(knowledge_points, weakness_items, resources, practice_answers, report)
        high_frequency_points = self._top_points(point_candidates, limit=8, weak_only=False)
        weak_points = self._top_points(point_candidates, limit=8, weak_only=True)
        if not weak_points:
            weak_points = high_frequency_points[:2]
        recommended_resource_ids = self._collect_recommended_resource_ids(resources, [*weak_points, *high_frequency_points])
        must_do_questions = self._build_must_do_questions([*weak_points, *high_frequency_points])
        easy_mistake_warnings = self._build_warnings(weak_points or high_frequency_points[:3])
        evidence_summary = self._build_evidence_summary(
            knowledge_points=knowledge_points,
            weakness_items=weakness_items,
            practice_answers=practice_answers,
            resources=resources,
            report=report,
            material_filter_count=material_filter_count,
        )
        task_specs = self._build_task_specs(
            duration_days=duration_days,
            now=now,
            points=weak_points + [point for point in high_frequency_points if point.knowledge_point_id not in {item.knowledge_point_id for item in weak_points}],
            resources=resources,
        )
        return {
            "kind": "exam_sprint",
            "duration_days": duration_days,
            "goal": goal,
            "strategy": "weakness_and_practice_first_then_high_frequency",
            "high_frequency_points": [self._point_payload(point, resources) for point in high_frequency_points],
            "weak_points": [self._point_payload(point, resources) for point in weak_points],
            "must_do_questions": [question.model_dump() for question in must_do_questions],
            "easy_mistake_warnings": [warning.model_dump() for warning in easy_mistake_warnings],
            "recommended_resource_ids": [str(resource_id) for resource_id in recommended_resource_ids],
            "evidence_summary": evidence_summary.model_dump(),
            "task_specs": task_specs,
        }

    def _point_payload(self, point: SprintPointCandidate, resources: list[GeneratedResource]) -> dict:
        return {
            "knowledge_point_id": point.knowledge_point_id,
            "title": point.title,
            "score": point.score,
            "reasons": point.reasons,
            "weak": point.weak,
            "recommended_resource_ids": [str(resource_id) for resource_id in self._recommend_resource_ids(resources, point.knowledge_point_id, point.title)],
        }

    def _score_points(
        self,
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
        practice_answers: list[PracticeAnswer],
        report: AssessmentReport | None,
    ) -> list[SprintPointCandidate]:
        by_id: dict[int | None, SprintPointCandidate] = {
            point.id: SprintPointCandidate(
                knowledge_point_id=point.id,
                title=point.title,
                score=max(10, 40 - point.order_index),
                reasons=["课程知识点和章节顺序"],
            )
            for point in knowledge_points
        }
        title_fallbacks: dict[str, SprintPointCandidate] = {}

        def candidate(point_id: int | None, title: str) -> SprintPointCandidate:
            if point_id in by_id:
                return by_id[point_id]
            key = " ".join(title.split()).casefold() or "期末冲刺重点"
            if key not in title_fallbacks:
                title_fallbacks[key] = SprintPointCandidate(knowledge_point_id=point_id, title=title or "期末冲刺重点")
            return title_fallbacks[key]

        for item in weakness_items:
            if item.status not in {"confirmed", "reviewing"}:
                continue
            row = candidate(item.knowledge_point_id, item.title)
            row.score += 70 if item.status == "reviewing" else 60
            row.reasons.append("来自已确认或复习中的弱点队列")
            row.weak = True

        for answer in practice_answers:
            feedback = answer.feedback_json or {}
            score = self._safe_int(feedback.get("score")) or 0
            if answer.is_correct is True and score >= 60:
                continue
            point_id = self._safe_int((answer.question_json or {}).get("knowledge_point_id"))
            title = str((answer.question_json or {}).get("knowledge_point_title") or "练习低分知识点")
            row = candidate(point_id, title)
            row.score += 55
            row.reasons.append("来自练习低分或错题")
            row.weak = True

        for resource in resources:
            row = candidate(resource.knowledge_point_id, resource.title)
            row.score += 10
            row.reasons.append("已有同课程资源可复用")

        report_json = report.report_json if report is not None else {}
        for item in report_json.get("weakness_list") or []:
            point_id = self._safe_int(item.get("knowledge_point_id") if isinstance(item, dict) else None)
            title = str(item.get("title") if isinstance(item, dict) else "" or "报告提示薄弱点")
            row = candidate(point_id, title)
            row.score += 35
            row.reasons.append("来自最新学习报告")
            row.weak = True

        return [*by_id.values(), *title_fallbacks.values()]

    @staticmethod
    def _top_points(candidates: list[SprintPointCandidate], limit: int, weak_only: bool) -> list[SprintPointCandidate]:
        pool = [item for item in candidates if item.weak or not weak_only]
        return sorted(pool, key=lambda item: (-item.score, item.title))[:limit]

    def _collect_recommended_resource_ids(self, resources: list[GeneratedResource], points: list[SprintPointCandidate]) -> list[int]:
        ids: list[int] = []
        for point in points:
            for resource_id in self._recommend_resource_ids(resources, point.knowledge_point_id, point.title):
                if resource_id not in ids:
                    ids.append(resource_id)
        if not ids:
            ids = [resource.id for resource in resources[:3]]
        return ids[:12]

    def _build_must_do_questions(self, points: list[SprintPointCandidate]) -> list[ExamSprintQuestion]:
        questions: list[ExamSprintQuestion] = []
        seen: set[str] = set()
        for point in points:
            key = str(point.knowledge_point_id or point.title)
            if key in seen:
                continue
            seen.add(key)
            question_type = "short_answer" if len(questions) % 3 == 0 else "single_choice"
            prompt = (
                f"用课程证据解释{point.title}的核心概念、常见误区和解题步骤。"
                if question_type == "short_answer"
                else f"围绕{point.title}完成 1 道选择题，并写出错因。"
            )
            questions.append(
                ExamSprintQuestion(
                    id=f"sprint-q{len(questions) + 1}",
                    knowledge_point_id=str(point.knowledge_point_id) if point.knowledge_point_id is not None else None,
                    title=point.title,
                    question_type=question_type,
                    prompt=prompt,
                    reason="来自弱点、练习低分或高频知识点。",
                )
            )
            if len(questions) >= 8:
                break
        return questions

    @staticmethod
    def _build_warnings(points: list[SprintPointCandidate]) -> list[ExamSprintWarning]:
        warnings: list[ExamSprintWarning] = []
        for point in points[:6]:
            warnings.append(
                ExamSprintWarning(
                    knowledge_point_id=str(point.knowledge_point_id) if point.knowledge_point_id is not None else None,
                    title=point.title,
                    warning=f"{point.title}：先复述概念边界，再做题；错题要标出依据缺口。",
                )
            )
        return warnings

    def _build_task_specs(
        self,
        duration_days: int,
        now: datetime,
        points: list[SprintPointCandidate],
        resources: list[GeneratedResource],
    ) -> list[SprintTaskSpec]:
        unique_points = self._dedupe_points(points)
        if not unique_points:
            unique_points = [SprintPointCandidate(None, "课程总复习", 1, ["课程复习"], False)]
        specs: list[SprintTaskSpec] = []
        for day_index in range(1, duration_days + 1):
            point = unique_points[(day_index - 1) % len(unique_points)]
            resource_ids = self._recommend_resource_ids(resources, point.knowledge_point_id, point.title)
            due_at = now + timedelta(days=day_index - 1)
            specs.append(
                SprintTaskSpec(
                    day_index=day_index,
                    title=f"第 {day_index} 天复习{point.title}",
                    task_type="sprint_review",
                    knowledge_point_id=point.knowledge_point_id,
                    reason="期末冲刺优先处理薄弱点和高频知识点。",
                    resource_ids=resource_ids,
                    due_at=due_at,
                    status="doing" if not specs else "todo",
                )
            )
            specs.append(
                SprintTaskSpec(
                    day_index=day_index,
                    title=f"完成{point.title}必刷题",
                    task_type="sprint_practice",
                    knowledge_point_id=point.knowledge_point_id,
                    reason="用确定性题型检查当天复习结果。",
                    resource_ids=resource_ids[:1],
                    due_at=due_at,
                    status="todo",
                )
            )
            if resource_ids:
                specs.append(
                    SprintTaskSpec(
                        day_index=day_index,
                        title=f"阅读{point.title}推荐资源",
                        task_type="sprint_resource",
                        knowledge_point_id=point.knowledge_point_id,
                        reason="复用同课程资源补足复习依据。",
                        resource_ids=resource_ids[:3],
                        due_at=due_at,
                        status="todo",
                    )
                )
        return specs

    @staticmethod
    def _dedupe_points(points: list[SprintPointCandidate]) -> list[SprintPointCandidate]:
        seen: set[str] = set()
        result: list[SprintPointCandidate] = []
        for point in points:
            key = str(point.knowledge_point_id) if point.knowledge_point_id is not None else " ".join(point.title.split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(point)
        return result

    def _build_response(self, path: LearningPath, tasks: list[LearningTask], resources: list[GeneratedResource]) -> ExamSprintPlanResponse:
        plan_json = path.plan_json or {}
        resources_by_id = {resource.id: resource for resource in resources}
        task_days = {str(key): int(value) for key, value in (plan_json.get("task_days") or {}).items()}
        created_at, updated_at = path_timestamps(path)
        return ExamSprintPlanResponse(
            id=str(path.id),
            course_id=str(path.course_id),
            agent_trace_id=getattr(path, "agent_trace_id", None),
            comparison_id=str(plan_json.get("comparison_id")) if plan_json.get("comparison_id") else None,
            trigger=str(plan_json.get("trigger") or "manual"),
            revision_of=str(plan_json.get("revision_of")) if plan_json.get("revision_of") else None,
            source_practice_session_id=(
                str(plan_json.get("source_practice_session_id")) if plan_json.get("source_practice_session_id") else None
            ),
            preserved_task_count=int(plan_json.get("preserved_task_count") or 0),
            generation_mode=str(plan_json.get("generation_mode") or "deterministic_source"),
            review_mode=str(plan_json.get("review_mode") or "rules_only"),
            review_result=dict(plan_json.get("review_result") or {}),
            warnings=[str(item) for item in plan_json.get("warnings") or []],
            duration_days=int(plan_json.get("duration_days") or 0),
            goal=path.goal,
            status=path.status,
            high_frequency_points=self._points_to_api(plan_json.get("high_frequency_points") or [], resources_by_id),
            weak_points=self._points_to_api(plan_json.get("weak_points") or [], resources_by_id),
            daily_tasks=[self._task_to_api(task, task_days.get(str(task.id), 1), resources_by_id) for task in tasks],
            must_do_questions=[ExamSprintQuestion(**item) for item in plan_json.get("must_do_questions") or []],
            easy_mistake_warnings=[ExamSprintWarning(**item) for item in plan_json.get("easy_mistake_warnings") or []],
            recommended_resources=[
                exam_sprint_resource_brief(resources_by_id[resource_id])
                for resource_id in self._json_resource_ids(plan_json.get("recommended_resource_ids") or [])
                if resource_id in resources_by_id
            ],
            evidence_summary=ExamSprintEvidenceSummary(**(plan_json.get("evidence_summary") or {})),
            created_at=created_at,
            updated_at=updated_at,
        )

    def _points_to_api(self, items: list[dict], resources_by_id: dict[int, GeneratedResource]) -> list[ExamSprintPoint]:
        points: list[ExamSprintPoint] = []
        for item in items:
            point_id = self._safe_int(item.get("knowledge_point_id"))
            title = str(item.get("title") or "冲刺重点")
            resource_ids = [resource_id for resource_id in self._json_resource_ids(item.get("recommended_resource_ids") or [])]
            points.append(
                ExamSprintPoint(
                    knowledge_point_id=str(point_id) if point_id is not None else None,
                    title=title,
                    reason="；".join(str(reason) for reason in item.get("reasons") or []) or str(item.get("reason") or "期末冲刺证据"),
                    score=int(item.get("score") or 0),
                    recommended_resource_ids=[str(resource_id) for resource_id in resource_ids],
                    recommended_resources=[
                        exam_sprint_resource_brief(resources_by_id[resource_id])
                        for resource_id in resource_ids
                        if resource_id in resources_by_id
                    ],
                )
            )
        return points

    def _task_to_api(
        self,
        task: LearningTask,
        day_index: int,
        resources_by_id: dict[int, GeneratedResource],
    ) -> ExamSprintDailyTask:
        resource_ids = self._json_resource_ids(task.recommended_resource_ids or [])
        return ExamSprintDailyTask(
            id=str(task.id),
            day_index=day_index,
            title=task.title,
            task_type=task.task_type,
            status=task.status,
            due_at=iso_timestamp(task.due_at),
            knowledge_point_id=str(task.knowledge_point_id) if task.knowledge_point_id is not None else None,
            reason=task.reason,
            recommended_resource_ids=[str(resource_id) for resource_id in resource_ids],
            recommended_resources=[
                exam_sprint_resource_brief(resources_by_id[resource_id])
                for resource_id in resource_ids
                if resource_id in resources_by_id
            ],
        )

    def _build_evidence_summary(
        self,
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
        practice_answers: list[PracticeAnswer],
        resources: list[GeneratedResource],
        report: AssessmentReport | None,
        material_filter_count: int,
    ) -> ExamSprintEvidenceSummary:
        active_weakness_count = sum(1 for item in weakness_items if item.status in {"confirmed", "reviewing"})
        low_score_count = sum(1 for answer in practice_answers if answer.is_correct is False or int((answer.feedback_json or {}).get("score") or 0) < 60)
        suggestions = []
        if report is not None:
            report_json = report.report_json or {}
            suggestions = [str(item) for item in report_json.get("next_step_suggestions") or []]
        basis = [
            f"课程知识点 {len(knowledge_points)} 个。",
            f"已确认或复习中的薄弱点 {active_weakness_count} 个。",
            f"练习低分或错题证据 {low_score_count} 条。",
            f"可推荐课程资源 {len(resources)} 个。",
        ]
        if material_filter_count:
            basis.append(f"已按 {material_filter_count} 份本课程资料限定证据范围。")
        return ExamSprintEvidenceSummary(
            knowledge_point_count=len(knowledge_points),
            weakness_count=active_weakness_count,
            practice_low_score_count=low_score_count,
            resource_count=len(resources),
            report_suggestion_count=len(suggestions),
            material_filter_count=material_filter_count,
            basis=basis,
        )

    @staticmethod
    def _recommend_resource_ids(resources: list[GeneratedResource], knowledge_point_id: int | None, title: str) -> list[int]:
        title_key = " ".join(title.split()).casefold()
        matched: list[GeneratedResource] = []
        if knowledge_point_id is not None:
            matched.extend([resource for resource in resources if resource.knowledge_point_id == knowledge_point_id])
        if len(matched) < 3 and title_key:
            matched.extend(
                [
                    resource
                    for resource in resources
                    if resource not in matched and title_key in " ".join(resource.title.split()).casefold()
                ]
            )
        return [resource.id for resource in matched[:3]]

    @staticmethod
    def _json_resource_ids(value: list) -> list[int]:
        ids: list[int] = []
        for item in value:
            try:
                ids.append(int(item))
            except (TypeError, ValueError):
                continue
        return ids

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
