"""Reuse committed pilot artifacts on explicit retries; no new model calls."""

from sqlalchemy import select

from backend.app.models import LearningPath
from backend.app.services.ai_job_contracts import AiJobConflictError
from backend.app.services.task_resource_binding import binding_status, exact_item


def recover_committed_result(repository, job, *, visited=frozenset()):
    if not job.retry_of_job_id or job.workflow not in {
        "resource_generation",
        "path_planning",
    }:
        return None
    original = repository.get_job(job.retry_of_job_id)
    if (
        original is None
        or original.user_id != job.user_id
        or original.course_id != job.course_id
        or original.workflow != job.workflow
    ):
        raise AiJobConflictError("恢复来源不存在或范围不一致。")
    if original.id in visited or original.id == job.id:
        raise AiJobConflictError("恢复来源形成循环，不能重新执行。")
    if original.request_json != job.request_json:
        raise AiJobConflictError("恢复请求与原任务不一致。")
    saved = dict(original.result_json or {})
    if not saved.pop("domain_committed", False):
        artifacts = repository.committed_pilot_artifacts(original)
        if not artifacts:
            return recover_committed_result(repository, original, visited=visited | {job.id})
        warning = "复用上次中断前已提交的产物；未重新执行生成。"
        request = original.request_json or {}
        if original.workflow == "path_planning":
            if len(artifacts) != 1:
                raise AiJobConflictError("恢复来源对应多个计划，不能自动选择。")
            path = artifacts[0]
            plan = path.plan_json or {}
            saved = {"course_id": original.course_id, "path_id": str(path.id),
                     "generation_mode": str(plan.get("generation_mode") or "model_generated"),
                     "preserved_task_count": int(plan.get("preserved_task_count") or 0),
                     "agent_trace_id": original.agent_trace_id, "warnings": [*plan.get("warnings", []), warning]}
        else:
            types = [item.resource_type for item in artifacts]
            if len(types) != len(set(types)) or not set(types).issubset(request.get("resource_types", [])):
                raise AiJobConflictError("恢复资源批次与原请求不一致。")
            point_ids = {item.knowledge_point_id for item in artifacts}
            if len(point_ids) != 1:
                raise AiJobConflictError("恢复资源知识点不一致。")
            point_id = next(iter(point_ids))
            saved = {"course_id": str(original.course_id), "knowledge_point_id": str(point_id) if point_id else None,
                     "path_task_id": str(request["path_task_id"]) if request.get("path_task_id") else None,
                     "evidence_chunk_ids": list(request.get("evidence_chunk_ids") or []),
                     "resource_ids": [str(item.id) for item in artifacts],
                     "failed_resource_types": [kind for kind in request.get("resource_types", []) if kind not in types], "warnings": [warning]}
    saved.pop("model_task_summary", None)
    if job.workflow == "path_planning":
        path = repository.db.scalar(
            select(LearningPath).where(
                LearningPath.id == int(saved.get("path_id") or 0),
                LearningPath.user_id == job.user_id,
                LearningPath.course_id == job.course_id,
            )
        )
        if path is None:
            raise AiJobConflictError("已提交计划不存在，请重新创建任务。")
    else:
        task_id = (job.request_json or {}).get("path_task_id")
        task = (
            repository.get_learning_task_for_user(job.user_id, int(task_id))
            if task_id
            else None
        )
        for resource_id in saved.get("resource_ids", []):
            resource = repository.get_resource_for_user(job.user_id, int(resource_id))
            if (
                resource is None
                or resource.course_id != job.course_id
                or resource.status != "completed"
                or resource.review_status != "passed"
            ):
                raise AiJobConflictError("已提交资源不存在或不可用，请重新创建任务。")
            if task_id and (
                task is None
                or binding_status(task, exact_item(task, resource.id) or {}, resource)
                != "verified"
            ):
                raise AiJobConflictError("已提交资源与任务版本不一致，不能自动恢复。")
    return saved
