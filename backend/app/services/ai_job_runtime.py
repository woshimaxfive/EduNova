from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from time import monotonic

from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models import AiJob
from backend.app.schemas.ai_jobs import iso_timestamp
from backend.app.services.ai_job_contracts import AiJobCancelled, AiJobTimeoutError


class AgentJobContext:
    def __init__(self, job_id: int, *, session_factory=SessionLocal, timeout_seconds: float | None = None) -> None:
        self.job_id = job_id
        self.session_factory = session_factory
        self.deadline = monotonic() + timeout_seconds if timeout_seconds is not None else None

    def _check_deadline(self) -> None:
        if self.deadline is not None and monotonic() >= self.deadline:
            raise AiJobTimeoutError("AI 任务执行超时。")

    def before_node(self, stage: str, label: str | None = None) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None:
                raise AiJobCancelled("任务已不存在。")
            if job.status in {"cancelling", "cancelled"} or job.cancel_requested_at is not None:
                now = datetime.now(UTC)
                job.status = "cancelled"
                job.stage = "cancelled"
                job.label = "任务已取消"
                job.completed_at = now
                job.heartbeat_at = now
                job.updated_at = now
                db.commit()
                raise AiJobCancelled("任务已取消。")
            self._check_deadline()
            job.heartbeat_at = datetime.now(UTC)
            job.stage = stage
            if label:
                job.label = label
            db.commit()

    def check_cancelled(self) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None or job.status in {"cancelling", "cancelled"} or job.cancel_requested_at is not None:
                raise AiJobCancelled("任务已取消。")
            self._check_deadline()
            job.heartbeat_at = datetime.now(UTC)
            db.commit()

    def record_model_usage(self, usage: dict[str, Any]) -> None:
        """Persist only aggregate model metrics; never persist prompts or model output."""
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None:
                return
            progress = dict(job.progress_json or {})
            summary = dict(progress.get("model_task_summary") or {})
            task_types = [str(item) for item in summary.get("task_types", []) if str(item)]
            task_type = str(usage.get("task_type") or "model_task")[:80]
            if task_type not in task_types:
                task_types.append(task_type)
            summary.update(
                {
                    "task_types": task_types[:16],
                    "call_count": int(summary.get("call_count") or 0) + 1,
                    "revision_count": int(summary.get("revision_count") or 0)
                    + (1 if "repair" in task_type or "revision" in task_type else 0),
                }
            )
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_latency_ms"):
                value = usage.get(key)
                if isinstance(value, int) and value >= 0:
                    summary[key] = int(summary.get(key) or 0) + value
            first_token_ms = usage.get("first_token_ms")
            if isinstance(first_token_ms, int) and first_token_ms >= 0:
                summary["first_token_ms"] = min(
                    int(summary.get("first_token_ms") or first_token_ms), first_token_ms
                )
            progress["model_task_summary"] = summary
            job.progress_json = progress
            db.commit()

    def after_node(
        self,
        *,
        name: str,
        label: str,
        progress_percent: int,
        status: str,
        resource_type: str | None = None,
    ) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None:
                return
            now = datetime.now(UTC)
            progress = dict(job.progress_json or {})
            steps = [dict(item) for item in progress.get("steps", []) if isinstance(item, dict)]
            key = f"{name}:{resource_type or ''}"
            item = {
                "name": name,
                "label": label,
                "status": status,
                "progress_percent": max(0, min(100, int(progress_percent))),
                "resource_type": resource_type,
                "updated_at": iso_timestamp(now),
                "_key": key,
            }
            existing_index = next((index for index, value in enumerate(steps) if value.get("_key") == key), None)
            if existing_index is None:
                steps.append(item)
            else:
                steps[existing_index] = item
            progress["steps"] = steps
            job.progress_json = progress
            job.progress_percent = max(int(job.progress_percent or 0), int(progress_percent))
            job.stage = name
            job.label = label
            job.heartbeat_at = now
            job.updated_at = now
            db.commit()
