from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    AiJob,
    AssessmentReport,
    Course,
    CourseEnrollment,
    CourseMaterialLink,
    LearningPath,
    LearningTask,
    Material,
    PracticeSession,
    User,
    WeaknessReviewItem,
    StudentProfile,
    GeneratedResource,
)
from backend.app.schemas.learning import LearningNextAction
from backend.app.services.courses import CourseService
from backend.app.services.mastery_progress import is_review_due


class LearningActionCourseNotFoundError(LookupError):
    pass


class LearningNextActionService:
    """Resolve one auditable next action from persisted learning state."""

    def __init__(self, db: Session, course_service: CourseService) -> None:
        self.db = db
        self.course_service = course_service

    def get_next_action(self, user: User, course_id: int | None = None) -> LearningNextAction:
        if course_id is not None:
            course = self._course_for_user(user.id, course_id)
            if course is None:
                raise LearningActionCourseNotFoundError("课程不存在或当前用户无权访问。")
            active_job = self._latest_active_job(user.id, course.id)
            if active_job is not None:
                job_action = self._job_action(active_job)
                if job_action is not None:
                    return job_action
            course_profile = self.course_service.get_learner_profile(user, course.id)
            if not course_profile.readiness.ready:
                return self._action(
                    "complete_profile",
                    f"完善《{course.title}》的学习目标与基础",
                    "补充这门课程自己的目标和基础后，路径与资源才能准确个性化。",
                    course_id=course.id,
                )
            return self._course_action(user, course)

        if not self._base_profile_ready(user.id):
            return self._action(
                "complete_profile",
                "完善基础学习画像",
                "告诉我偏好的学习方式或学习节奏，后续课程才能真正按你调整。",
            )

        course = self._latest_course(user.id)
        material = self._latest_unassigned_material(user.id)
        if material is not None and material.ingestion_status == "stored":
            material = None
        if course is None:
            return self._material_action(material)
        course_profile = self.course_service.get_learner_profile(user, course.id)
        if not course_profile.readiness.ready:
            return self._action(
                "complete_profile",
                f"完善《{course.title}》的学习目标与基础",
                "课程画像只用于这门课，不会污染其他课程。你仍可继续浏览和提问。",
                course_id=course.id,
            )
        if material is not None and self._material_activity_at(material) > self._course_activity_at(course):
            return self._material_action(material)
        return self._course_action(user, course)

    def _course_action(self, user: User, course: Course) -> LearningNextAction:
        weaknesses = list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(
                    WeaknessReviewItem.user_id == user.id,
                    WeaknessReviewItem.course_id == course.id,
                    WeaknessReviewItem.status != "dismissed",
                )
                .order_by(WeaknessReviewItem.updated_at.desc(), WeaknessReviewItem.id.desc())
            )
        )
        pending = next((item for item in weaknesses if item.status == "pending"), None)
        if pending is not None:
            return self._action(
                "confirm_weakness",
                f"确认薄弱点：{pending.title}",
                "确认后再安排针对性学习；不符合实际也可以忽略。",
                course_id=course.id,
                knowledge_point_id=pending.knowledge_point_id,
                weakness_item_id=pending.id,
            )

        path = self.db.scalar(
            select(LearningPath)
            .where(
                LearningPath.user_id == user.id,
                LearningPath.course_id == course.id,
                LearningPath.status == "active",
            )
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )
        tasks = list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.path_id == path.id)
                .order_by(LearningTask.created_at.asc(), LearningTask.id.asc())
            )
        ) if path is not None else []
        current_task = next((task for task in tasks if task.status == "doing"), None)
        current_task = current_task or next((task for task in tasks if task.status in {"todo", "pending"}), None)
        if current_task is not None:
            resource_id = self._first_resource_id(current_task)
            return self._action(
                "continue_path_task",
                f"继续任务：{current_task.title}",
                current_task.reason or "继续当前学习路径，完成后再用练习更新掌握度。",
                course_id=course.id,
                knowledge_point_id=current_task.knowledge_point_id,
                path_task_id=current_task.id,
                resource_id=resource_id,
            )

        active_weakness = next((item for item in weaknesses if item.status in {"reviewing", "confirmed"}), None)
        if active_weakness is not None:
            return self._action(
                "practice_weakness",
                f"针对练习：{active_weakness.title}",
                "通过自适应练习验证这个薄弱点是否已经掌握。",
                course_id=course.id,
                knowledge_point_id=active_weakness.knowledge_point_id,
                weakness_item_id=active_weakness.id,
            )

        due_review = next((item for item in weaknesses if is_review_due(item)), None)
        if due_review is not None:
            return self._action(
                "practice_weakness",
                f"到期复习：{due_review.title}",
                "这个知识点已攻克并到达间隔复习时间，用一次短练习确认掌握仍然稳定。",
                course_id=course.id,
                knowledge_point_id=due_review.knowledge_point_id,
                weakness_item_id=due_review.id,
            )

        mastery = self.course_service.get_mastery_map(user, course.id)
        low_point = next(
            (
                point
                for point in sorted(
                    mastery.points,
                    key=lambda item: (item.score is None, item.score if item.score is not None else 101, item.order_index),
                )
                if point.score is not None and point.score < 75
            ),
            None,
        )
        if low_point is not None:
            return self._action(
                "practice_weakness",
                f"练习薄弱知识点：{low_point.title}",
                f"当前掌握度 {low_point.score}%，先用针对性练习巩固。",
                course_id=course.id,
                knowledge_point_id=int(low_point.id),
            )

        if path is None:
            return self._action(
                "generate_path",
                "生成个性化学习路径",
                "根据课程结构、学习画像和已有证据安排学习顺序。",
                course_id=course.id,
            )

        latest_practice = self.db.scalar(
            select(PracticeSession)
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.course_id == course.id,
                PracticeSession.status == "completed",
            )
            .order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc())
        )
        latest_report = self.db.scalar(
            select(AssessmentReport)
            .where(AssessmentReport.user_id == user.id, AssessmentReport.course_id == course.id)
            .order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        )
        path_completed = bool(tasks) and all(task.status == "completed" for task in tasks)
        if path_completed and latest_practice is not None and self._report_is_stale(latest_report, latest_practice):
            return self._action(
                "update_report",
                "生成最新学习报告",
                "学习路径已经完成，使用最新练习结果生成阶段总结。",
                course_id=course.id,
            )

        unassessed = next((point for point in mastery.points if point.score is None), None)
        if unassessed is not None:
            return self._action(
                "study_knowledge_point",
                f"学习知识点：{unassessed.title}",
                "先阅读课程内容，再通过练习形成有效掌握度证据。",
                course_id=course.id,
                knowledge_point_id=int(unassessed.id),
            )

        if latest_report is None or self._report_is_stale(latest_report, latest_practice):
            return self._action(
                "update_report",
                "更新学习报告",
                "把最近的学习结果整理成可复盘的阶段报告。",
                course_id=course.id,
            )
        completion = self.course_service.get_stage_completion(user, course.id)
        if completion.eligible:
            return self._action(
                "complete_course",
                "完成并归档这门课程",
                "本阶段路径、掌握度、薄弱点、练习和报告均已达标。归档不会删除任何学习记录。",
                course_id=course.id,
            )
        return self._action(
            "review_report",
            "查看阶段学习报告",
            "回顾掌握度、薄弱点和下一阶段建议。",
            course_id=course.id,
        )

    def _material_action(self, material: Material | None) -> LearningNextAction:
        if material is None:
            return self._action("upload_material", "上传第一份学习资料", "支持 PDF、DOCX 和 PPTX，解析后可直接生成课程。")
        if material.parse_status == "failed" or material.ingestion_status == "failed":
            return self._action(
                "retry_material",
                f"重新解析：{material.filename}",
                "上次解析没有完成，原文件仍然保留。",
                status="blocked",
                material_id=material.id,
            )
        if material.ingestion_status == "awaiting_confirmation":
            return self._action(
                "review_material",
                f"确认目录：{material.filename}",
                "检查章节、页码和解析质量，确认后才能生成课程。",
                material_id=material.id,
            )
        if material.ingestion_status == "confirmed":
            return self._action(
                "create_course",
                f"用《{material.filename}》生成课程",
                "目录已经确认，可以生成知识点和学习任务。",
                material_id=material.id,
            )
        return self._action(
            "wait_for_material",
            f"正在解析：{material.filename}",
            "解析会在后台继续，完成后需要确认目录。",
            status="waiting",
            material_id=material.id,
        )

    def _job_action(self, job: AiJob) -> LearningNextAction | None:
        if job.workflow == "material_ingestion":
            material_id = self._positive_int((job.request_json or {}).get("material_id"))
            return self._action(
                "wait_for_material",
                job.label or "正在解析资料",
                "任务会在后台继续，完成后进入资料库确认目录。",
                status="waiting",
                material_id=material_id,
            )
        if job.workflow == "course_builder":
            return self._action(
                "wait_for_course",
                job.label or "正在生成课程",
                "课程会在后台生成，完成后可直接进入课程空间。",
                status="waiting",
                course_id=job.course_id,
            )
        if job.workflow == "path_planning":
            course_id = self._positive_int((job.request_json or {}).get("course_id")) or job.course_id
            return self._action(
                "wait_for_path",
                job.label or "正在规划学习路径",
                "路径会在后台继续生成，完成后可直接恢复当前课程的学习任务。",
                status="waiting",
                course_id=course_id,
            )
        if job.workflow == "practice_generation":
            course_id = self._positive_int((job.request_json or {}).get("course_id")) or job.course_id
            return self._action(
                "wait_for_practice",
                job.label or "正在生成针对练习",
                "练习会在后台继续生成，完成后可直接开始作答。",
                status="waiting",
                course_id=course_id,
            )
        if job.workflow == "report_generation":
            course_id = self._positive_int((job.request_json or {}).get("course_id")) or job.course_id
            return self._action(
                "wait_for_report",
                job.label or "正在更新学习报告",
                "报告会在后台继续生成，完成后可查看最新学习总结。",
                status="waiting",
                course_id=course_id,
            )
        return None

    def _course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def _latest_course(self, user_id: int) -> Course | None:
        return self.db.scalar(
            select(Course)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(
                Course.owner_id == user_id,
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.learning_status == "active",
            )
            .order_by(CourseEnrollment.last_accessed_at.desc().nullslast(), CourseEnrollment.created_at.desc(), Course.id.desc())
        )

    def _base_profile_ready(self, user_id: int) -> bool:
        profile = self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))
        if profile is None:
            return False
        values = profile.profile_json or {}
        confidence = profile.dimension_confidence_json or {}
        return any(
            bool(str(values.get(key) or "").strip()) and float(confidence.get(key, 0) or 0) >= 50
            for key in ("learning_preference", "learning_pace")
        )

    def _latest_unassigned_material(self, user_id: int) -> Material | None:
        return self.db.scalar(
            select(Material)
            .where(
                Material.user_id == user_id,
                Material.ingestion_status != "stored",
                ~select(CourseMaterialLink.id).where(CourseMaterialLink.material_id == Material.id).exists(),
            )
            .order_by(Material.created_at.desc(), Material.id.desc())
        )

    def _latest_active_job(self, user_id: int, course_id: int | None = None) -> AiJob | None:
        statement = select(AiJob).where(
            AiJob.user_id == user_id,
            AiJob.workflow.in_(
                (
                    "material_ingestion",
                    "course_builder",
                    "path_planning",
                    "practice_generation",
                    "report_generation",
                )
            ),
            AiJob.status.in_(("queued", "running", "cancelling")),
        )
        if course_id is not None:
            statement = statement.where(AiJob.course_id == course_id)
        return self.db.scalar(statement.order_by(AiJob.updated_at.desc(), AiJob.id.desc()))

    def _first_resource_id(self, task: LearningTask) -> int | None:
        for value in task.recommended_resource_ids or []:
            parsed = LearningNextActionService._positive_int(value)
            if parsed is not None and self._valid_task_resource(task, parsed):
                return parsed
        bundle = task.learning_bundle_json if isinstance(task.learning_bundle_json, dict) else {}
        for item in bundle.get("items", []):
            if not isinstance(item, dict) or item.get("learning_status") == "completed":
                continue
            parsed = self._positive_int(item.get("resource_id"))
            if parsed is not None and self._valid_task_resource(task, parsed):
                return parsed
        return None

    def _valid_task_resource(self, task: LearningTask, resource_id: int) -> bool:
        return self.db.scalar(select(GeneratedResource.id).where(
            GeneratedResource.id == resource_id,
            GeneratedResource.user_id == task.user_id,
            GeneratedResource.course_id == task.course_id,
            GeneratedResource.status == "completed",
        )) is not None

    @staticmethod
    def _report_is_stale(report: AssessmentReport | None, practice: PracticeSession | None) -> bool:
        if report is None:
            return practice is not None
        if practice is None:
            return False
        if report.practice_session_id != practice.id:
            return True
        return LearningNextActionService._aware(practice.updated_at) > LearningNextActionService._aware(report.created_at)

    @staticmethod
    def _material_activity_at(material: Material) -> datetime:
        return LearningNextActionService._aware(material.parsed_at or material.created_at)

    @staticmethod
    def _course_activity_at(course: Course) -> datetime:
        return LearningNextActionService._aware(course.updated_at or course.created_at)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @staticmethod
    def _positive_int(value: object) -> int | None:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _action(
        kind: str,
        label: str,
        description: str,
        *,
        status: str = "ready",
        course_id: int | None = None,
        material_id: int | None = None,
        knowledge_point_id: int | None = None,
        path_task_id: int | None = None,
        resource_id: int | None = None,
        weakness_item_id: int | None = None,
    ) -> LearningNextAction:
        return LearningNextAction(
            kind=kind,
            status=status,
            label=label,
            description=description,
            course_id=str(course_id) if course_id is not None else None,
            material_id=str(material_id) if material_id is not None else None,
            knowledge_point_id=str(knowledge_point_id) if knowledge_point_id is not None else None,
            path_task_id=str(path_task_id) if path_task_id is not None else None,
            resource_id=str(resource_id) if resource_id is not None else None,
            weakness_item_id=str(weakness_item_id) if weakness_item_id is not None else None,
        )
