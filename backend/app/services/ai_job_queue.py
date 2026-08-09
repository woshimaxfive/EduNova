from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.core.observability import get_tracer


class RqAiJobQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, job_id: int) -> str:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.ai_jobs import run_ai_job

        queue_job_id = f"ai-job-{job_id}"
        connection = Redis.from_url(self.settings.redis_url)
        queue = Queue(self.settings.ai_job_queue_name, connection=connection)
        with get_tracer(__name__).start_as_current_span(
            "edunova.ai_job.enqueue",
            attributes={"edunova.job.id": job_id, "messaging.destination.name": self.settings.ai_job_queue_name},
        ):
            queue.enqueue(
                run_ai_job,
                job_id,
                job_id=queue_job_id,
                job_timeout=self.settings.ai_job_timeout_seconds,
                result_ttl=86400,
                failure_ttl=86400,
            )
        return queue_job_id

    def cancel(self, queue_job_id: str) -> None:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(self.settings.redis_url)
        try:
            Job.fetch(queue_job_id, connection=connection).cancel()
        except Exception:
            return

    def is_active(self, queue_job_id: str) -> bool:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(self.settings.redis_url)
        try:
            return Job.fetch(queue_job_id, connection=connection).get_status(refresh=True) in {
                "queued",
                "started",
                "deferred",
                "scheduled",
            }
        except Exception:
            return False
