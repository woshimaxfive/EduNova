from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from backend.app.agents.assessment_contracts import (
    AssessmentState,
)
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope


class AssessmentRuntimeMixin:
    def _run_node(
        self,
        state: AssessmentState,
        agent_name: str,
        step_index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        job_context = state.get("job_context")
        if job_context is not None:
            job_context.before_node(agent_name, input_summary)
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
                result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record_failure(state, agent_name, step_index, input_summary, exc, started)
            if job_context is not None:
                job_context.after_node(
                    name=agent_name,
                    label="练习生成节点失败",
                    progress_percent=min(95, step_index * 15),
                    status="failed",
                )
            raise
        self._record(state, agent_name, step_index, status, input_summary, output_summary, metadata, started)
        if job_context is not None:
            job_context.after_node(
                name=agent_name,
                label=input_summary,
                progress_percent=min(95, step_index * 15),
                status=status,
            )
        return result

    def _record_failure(self, state: AssessmentState, agent_name: str, step_index: int, input_summary: str, exc: Exception, started: float) -> None:
        self._record(state, agent_name, step_index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)

    def _record(
        self,
        state: AssessmentState,
        agent_name: str,
        step_index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        metadata: dict[str, Any],
        started: float,
    ) -> None:
        recorder = self.service.trace_recorder
        if recorder is None:
            return
        recorder.record(
            trace_id=state["trace_id"],
            user_id=int(state["user_id"]),
            course_id=int(state.get("course_id") or 0) or None,
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="practice_session",
            artifact_id=metadata.get("artifact_id"),
            metadata={"operation": state.get("operation"), **metadata},
        )
