"""Immutable terminal metadata, not executable LangGraph checkpoints or grades."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json

from sqlalchemy import select
from pydantic import ValidationError

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError
from backend.app.models import LearningPath, LearningTask
from backend.app.schemas.agents import safe_agent_summary
from backend.app.schemas.run_history import RunSnapshot
from backend.app.services.ai_job_contracts import TERMINAL_STATUSES
from backend.app.services.paths import PathService, SqlAlchemyPathRepository


def content_hash(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def path_content(path, tasks):
    return {"id": path.id, "title": path.title, "goal": path.goal, "plan": path.plan_json,
            "tasks": [{"id": task.id, "title": task.title, "type": task.task_type, "point": task.knowledge_point_id,
                       "bundle": task.learning_bundle_json, "resources": task.recommended_resource_ids} for task in tasks]}


def validate_snapshot(payload):
    try:
        snapshot = RunSnapshot.model_validate(payload)
    except ValidationError:
        raise ConflictDomainError("运行快照格式不受支持，不能重放或执行。") from None
    if content_hash(snapshot.model_dump(exclude={"digest"})) != snapshot.digest:
        raise ConflictDomainError("运行快照校验失败，不能重放或执行。")
    return snapshot


class RunHistoryService:
    def __init__(self, job_service):
        self.jobs = job_service
        self.repo = job_service.repository

    def replay(self, user, job_id):
        # Deliberately bypass get_job: that endpoint reconciles stale job state.
        job = self.jobs._require(user, job_id)
        payload = (job.progress_json or {}).get("snapshot")
        if not payload:
            raise NotFoundDomainError("尚未保存运行快照。")
        snapshot = validate_snapshot(payload)
        if snapshot.job_id != str(job.id) or snapshot.trace_id != job.agent_trace_id:
            raise ConflictDomainError("快照与运行身份不一致。")
        return snapshot

    def capture(self, user, job_id):
        try:
            job = self.jobs._require(user, job_id, for_update=True)
            existing = (job.progress_json or {}).get("snapshot")
            if existing:
                result = validate_snapshot(existing)
                self.repo.rollback()
                return result
            if job.status not in TERMINAL_STATUSES:
                raise ConflictDomainError("只能保存已结束运行的快照。")
            raw = job.result_json or {}
            keys = {"course_id", "path_id", "resource_ids", "session_id", "report_id", "material_id", "domain_committed"}
            refs = {}
            for key, value in raw.items():
                if key not in keys:
                    continue
                if key == "domain_committed" and type(value) is bool:
                    refs[key] = value
                elif key == "resource_ids" and isinstance(value, list):
                    refs[key] = [str(item) for item in value if str(item).isdigit() and int(item) > 0]
                elif str(value).isdigit() and int(value) > 0:
                    refs[key] = str(value)
            path_hash = None
            if job.workflow == "path_planning" and refs.get("path_id"):
                path_repo = SqlAlchemyPathRepository(self.repo.db)
                path = path_repo.get_path_for_user(user.id, int(refs["path_id"]))
                if path is not None and path.course_id == job.course_id:
                    path_hash = content_hash(path_content(path, path_repo.list_tasks_for_path(path.id)))
            steps = [{"name": safe_agent_summary(str(item.get("name") or ""), "步骤"),
                      "status": str(item.get("status") or "unknown")[:32],
                      "label": safe_agent_summary(str(item.get("label") or ""), "执行步骤")}
                     for item in (job.progress_json or {}).get("steps", []) if isinstance(item, dict)]
            metrics = (job.progress_json or {}).get("model_task_summary") or {}
            telemetry = {key: value for key, value in metrics.items() if key in {
                "call_count", "revision_count", "input_tokens", "output_tokens", "reasoning_tokens", "total_latency_ms", "first_token_ms"
            } and type(value) is int and value >= 0}
            payload = dict(schema_version=1, job_id=str(job.id), workflow=job.workflow, status=job.status,
                course_id=str(job.course_id) if job.course_id else None,
                parent_job_id=str(job.retry_of_job_id) if job.retry_of_job_id else None,
                trace_id=job.agent_trace_id, captured_at=datetime.now(UTC).isoformat(), artifact_refs=refs, request_hash=content_hash(job.request_json or {}),
                path_content_hash=path_hash, steps=steps, telemetry=telemetry, error_code=job.error_code)
            snapshot = RunSnapshot(**payload, digest=content_hash(payload))
            job.progress_json = {**(job.progress_json or {}), "snapshot": snapshot.model_dump()}
            self.repo.commit()
            return snapshot
        except Exception:
            self.repo.rollback()
            raise

    def _expected(self, user, job_id, digest):
        snapshot = self.replay(user, job_id)
        if snapshot.digest != digest:
            raise ConflictDomainError("快照版本不一致，请重新读取。")
        return snapshot

    def branch(self, user, job_id, payload):
        snapshot = self._expected(user, job_id, payload.expected_digest)
        if snapshot.workflow != "path_planning" or not snapshot.path_content_hash:
            raise ConflictDomainError("此运行不支持计划分支，请使用对应领域入口。")
        db = self.repo.db
        path_repo = SqlAlchemyPathRepository(db)
        paths = PathService(path_repo)
        course_id = int(snapshot.course_id)
        try:
            paths._require_course(user, course_id)
            if path_repo.lock_course(user.id, course_id) is None or not path_repo.is_course_active(user.id, course_id):
                raise ConflictDomainError("课程不可执行，请先恢复学习。")
            existing = db.scalar(select(LearningPath).where(LearningPath.user_id == user.id, LearningPath.course_id == course_id,
                LearningPath.plan_json["branch_snapshot"].astext == snapshot.digest))
            if existing is not None:
                db.rollback()
                return paths.get_path_version(user, existing.id)
            active = path_repo.get_active_path(user.id, course_id)
            if (active.id if active else None) != payload.expected_active_path_id:
                raise ConflictDomainError("当前计划已变化，不能创建分支。")
            source = path_repo.get_path_for_user(user.id, int(snapshot.artifact_refs["path_id"]))
            if source is None or source.course_id != course_id:
                raise NotFoundDomainError("源计划不存在。")
            tasks = path_repo.list_tasks_for_path(source.id)
            if content_hash(path_content(source, tasks)) != snapshot.path_content_hash:
                raise ConflictDomainError("源计划内容或任务绑定已变化，不能从旧快照分支。")
            branch = path_repo.add_path(LearningPath(user_id=user.id, course_id=course_id, title=source.title, goal=source.goal,
                status="draft", approval_status="draft", plan_json={**deepcopy(source.plan_json or {}),
                    "revision_of": payload.expected_active_path_id, "branched_from": source.id, "branch_snapshot": snapshot.digest,
                    "preserved_task_count": 0, "trigger": "manual", "assessment_session_id": None}))
            for task in tasks:
                path_repo.add_task(LearningTask(user_id=user.id, course_id=course_id, path_id=branch.id,
                    knowledge_point_id=task.knowledge_point_id, title=task.title, task_type=task.task_type, reason=task.reason,
                    recommended_resource_ids=deepcopy(task.recommended_resource_ids), learning_bundle_json=deepcopy(task.learning_bundle_json), status="todo"))
            db.commit()
            return paths.get_path_version(user, branch.id)
        except Exception:
            db.rollback()
            raise

    def reexecute(self, user, job_id, digest, key):
        snapshot = self._expected(user, job_id, digest)
        if snapshot.workflow not in {"path_planning", "resource_generation"}:
            raise ConflictDomainError("此能力不支持通用重新执行，请使用对应领域入口。")
        original = self.jobs._require(user, job_id)
        if content_hash(original.request_json or {}) != snapshot.request_hash:
            raise ConflictDomainError("原运行输入已变化，不能从此快照重新执行。")
        request = deepcopy(original.request_json)
        if snapshot.workflow == "path_planning":
            request["draft"] = True
        elif request.get("path_task_id"):
            raise ConflictDomainError("固定任务资源不能被重新执行覆盖，请先创建计划分支。")
        def lineage(job):
            job.progress_json = {**job.progress_json, "reexecuted_from": original.id, "source_snapshot": snapshot.digest}
        return self.jobs._create(user, workflow=snapshot.workflow, course_id=original.course_id,
            request_json=request, idempotency_key=f"reexecute-{job_id}-{content_hash(key)}", before_commit=lineage)
