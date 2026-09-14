"""Read-only evidence projection; never promotes user marks into mastery."""

from sqlalchemy import select

from backend.app.core.errors import NotFoundDomainError
from backend.app.models import (
    Course,
    GeneratedResource,
    LearningPath,
    LearningTask,
    PracticeSession,
    ResourceInteraction,
)
from backend.app.schemas.task_progress import TaskProgress
from backend.app.services.task_resource_binding import binding_status


def project_task_progress(task, path, resources, events, sessions, mastery=None):
    items = [
        item
        for item in (task.learning_bundle_json or {}).get("items", [])
        if isinstance(item, dict)
    ]
    blockers = []
    if path.approval_status != "approved":
        blockers.append("计划尚未批准，历史标记不能作为批准证据。")
    completed = 0
    event_ids, assessment_ids = [], []
    assessment_results = []
    next_resource = None
    next_step = None
    for item in items:
        raw_id = str(item.get("resource_id") or "")
        resource = resources.get(int(raw_id)) if raw_id.isdigit() else None
        valid = binding_status(task, item, resource) == "verified"
        if not valid:
            blockers.append(
                f"{item.get('resource_type', '资源')}缺少可验证绑定或版本已变化。"
            )
            if item.get("resource_type") == "quiz":
                assessment_results.append(False)
            continue
        matching_events = [
            event
            for event in events
            if event.path_task_id == task.id
            and event.resource_id == resource.id
            and event.event_type == "completed"
            and (event.evidence_json or {}).get("path_id") == task.path_id
            and (event.evidence_json or {}).get("task_id") == task.id
            and (event.evidence_json or {}).get("binding_status") == "verified"
            and (event.evidence_json or {}).get("resource") == item.get("binding")
        ]
        matching_sessions = [
            session
            for session in sessions
            if (session.assessment_json or {}).get("source_binding", {}).get("task_id")
            == task.id
            and (session.assessment_json or {}).get("source_binding", {}).get("path_id")
            == task.path_id
            and (session.assessment_json or {})
            .get("source_binding", {})
            .get("resource")
            == item.get("binding")
        ]
        is_quiz = item.get("resource_type") == "quiz"
        finished = [
            session for session in matching_sessions if session.status == "completed"
        ]
        activity_done = bool(finished) if is_quiz else bool(matching_events)
        if is_quiz:
            passed = any(
                session.score is not None
                and float(session.score) >= 80
                and (session.assessment_json or {}).get("grading_status") == "complete"
                for session in finished
            )
            assessment_results.append(passed)
            assessment_ids.extend(str(session.id) for session in finished)
            if not passed and next_step is None:
                next_step, next_resource = (
                    ("review_assessment" if finished else "take_assessment"),
                    str(resource.id),
                )
        elif not activity_done and next_step is None:
            next_step, next_resource = "study_resource", str(resource.id)
        completed += int(activity_done)
        event_ids.extend(event.event_id for event in matching_events)
    activity_completed = bool(items) and completed == len(items) and not blockers
    assessment_passed = (
        bool(assessment_results) and all(assessment_results) and not blockers
    )
    mastered = bool(mastery and mastery.status == "mastered")
    if not items:
        blockers.append("任务没有必需活动，不能推断已完成。")
    return TaskProgress(
        task_id=str(task.id),
        path_id=str(task.path_id),
        user_reported_completed=task.status == "completed",
        activity_completed=activity_completed,
        assessment_passed=assessment_passed,
        mastered=mastered,
        mastery_score=mastery.score if mastery else None,
        mastery_status=mastery.status if mastery else "not_started",
        required_activity_count=len(items),
        completed_activity_count=completed,
        assessment_session_ids=list(dict.fromkeys(assessment_ids)),
        event_ids=list(dict.fromkeys(event_ids)),
        blocked_reasons=blockers,
        next_step="resolve_binding" if blockers else next_step or "continue_learning",
        next_resource_id=None if blockers else next_resource,
    )


class TaskProgressService:
    def __init__(self, db, course_service):
        self.db, self.course_service = db, course_service

    def get(self, user, task_id):
        task = self.db.scalar(
            select(LearningTask).where(
                LearningTask.id == task_id, LearningTask.user_id == user.id
            )
        )
        path = self.db.get(LearningPath, task.path_id) if task else None
        course = (
            self.db.get(Course, task.course_id) if task and task.course_id else None
        )
        if (
            task is None
            or path is None
            or path.user_id != user.id
            or course is None
            or course.owner_id != user.id
            or path.course_id != course.id
        ):
            raise NotFoundDomainError("任务不存在或无权访问。")
        resources = {
            resource.id: resource
            for resource in self.db.scalars(
                select(GeneratedResource).where(
                    GeneratedResource.user_id == user.id,
                    GeneratedResource.course_id == course.id,
                )
            )
        }
        events = list(
            self.db.scalars(
                select(ResourceInteraction).where(
                    ResourceInteraction.user_id == user.id,
                    ResourceInteraction.path_task_id == task.id,
                )
            )
        )
        sessions = list(
            self.db.scalars(
                select(PracticeSession).where(
                    PracticeSession.user_id == user.id,
                    PracticeSession.course_id == course.id,
                )
            )
        )
        mastery = self.course_service.get_mastery_map(user, course.id)
        point = next(
            (
                point
                for point in mastery.points
                if point.id == str(task.knowledge_point_id)
            ),
            None,
        )
        return project_task_progress(task, path, resources, events, sessions, point)
