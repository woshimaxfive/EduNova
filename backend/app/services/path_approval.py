from __future__ import annotations

from datetime import UTC, datetime

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError, ValidationDomainError
from backend.app.models import User
from backend.app.schemas.paths import LearningPathDetail, LearningPathResponse, path_to_api
from backend.app.services.task_resource_binding import binding_status


class PathApprovalMixin:
    def get_path_version(self, user: User, path_id: int) -> LearningPathDetail:
        path = self.repository.get_path_for_user(user.id, path_id)
        if path is None or path.course_id is None:
            raise NotFoundDomainError("计划版本不存在或无权访问。")
        course = self._require_course(user, int(path.course_id))
        return self._build_detail(
            user, course, path, self.repository.list_tasks_for_path(path.id),
            self.repository.list_generated_resources(user.id, course.id),
            self.repository.list_knowledge_points(course.id),
            self.repository.list_weakness_review_items(user.id, course.id),
        )

    def list_drafts(self, user: User, course_id: int) -> list[LearningPathResponse]:
        self._require_course(user, course_id)
        return [path_to_api(path) for path in self.repository.list_drafts(user.id, course_id)]

    def approve_path(self, user: User, path_id: int, expected_active_path_id: int | None) -> LearningPathDetail:
        path = self.repository.get_path_for_user(user.id, path_id)
        if path is None or path.course_id is None:
            raise NotFoundDomainError("计划版本不存在或无权访问。")
        course_id = int(path.course_id)
        try:
            if self.repository.lock_course(user.id, course_id) is None:
                raise NotFoundDomainError("课程不存在或无权访问。")
            if not self.repository.is_course_active(user.id, course_id):
                raise ValidationDomainError("课程已归档，请先恢复学习。")
            path = self.repository.get_path_for_user(user.id, path_id)
            if path is None:
                raise NotFoundDomainError("计划版本已不存在。")
            raw_base = (path.plan_json or {}).get("revision_of")
            base_id = int(raw_base) if str(raw_base).isdigit() else None
            if base_id != expected_active_path_id:
                raise ConflictDomainError("确认的基础版本与草稿不一致，请重新读取计划。")
            active = self.repository.get_active_path(user.id, course_id)
            active_id = active.id if active is not None else None
            if path.approval_status == "approved" and active_id == path.id:
                self.repository.rollback()
                return self.get_path_version(user, path.id)
            if path.approval_status != "draft" or path.status != "draft":
                raise ConflictDomainError("只能批准待确认草稿；历史计划不能补造确认记录。")
            if active_id != expected_active_path_id:
                raise ConflictDomainError("当前计划已变化，请生成新草稿后确认。")
            if not self.repository.list_tasks_for_path(path.id):
                raise ValidationDomainError("空计划不能批准。")
            resources = {item.id: item for item in self.repository.list_generated_resources(user.id, course_id)}
            for task in self.repository.list_tasks_for_path(path.id):
                for item in (task.learning_bundle_json or {}).get("items", []):
                    if isinstance(item, dict) and item.get("resource_id") is not None:
                        raw_id = str(item["resource_id"])
                        resource = resources.get(int(raw_id)) if raw_id.isdigit() else None
                        if binding_status(task, item, resource) != "verified":
                            raise ConflictDomainError("草稿资源缺失、未经验证或版本已变化，请重新生成草稿。")
            self.repository.archive_active_paths(user.id, course_id)
            path.status = "active"
            path.approval_status = "approved"
            path.approved_at = datetime.now(UTC)
            path.updated_at = path.approved_at
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.get_path_version(user, path_id)
