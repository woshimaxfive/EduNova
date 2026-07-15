import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

import {
  getResourceLearningState,
  recordResourceInteraction,
  type GeneratedResource,
  type ResourceFeedback
} from "../../api/resources";

const feedbackOptions: Array<{ value: ResourceFeedback; label: string }> = [
  { value: "helpful", label: "有帮助" },
  { value: "too_hard", label: "太难" },
  { value: "too_easy", label: "太简单" },
  { value: "not_helpful", label: "没帮助" }
];

function eventId() {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}_${Math.random().toString(36).slice(2)}`;
  return `evt_${id}`;
}

export function ResourceLearningControls({ resource }: { resource: GeneratedResource }) {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const openedResource = useRef<string | null>(null);
  const resourceId = Number.parseInt(resource.id, 10);
  const rawTaskId = searchParams.get("path_task_id");
  const pathTaskId = rawTaskId && /^\d+$/.test(rawTaskId) ? Number.parseInt(rawTaskId, 10) : null;
  const stateQuery = useQuery({
    queryKey: ["resources", "learning-state", resource.id],
    queryFn: () => getResourceLearningState(resourceId),
    enabled: Number.isFinite(resourceId)
  });
  const recordInteraction = (input: { eventType: "opened" | "started" | "completed" | "feedback"; feedback?: ResourceFeedback }) =>
    recordResourceInteraction(resourceId, {
      event_id: eventId(),
      event_type: input.eventType,
      path_task_id: pathTaskId,
      feedback: input.feedback
    });
  const refreshLearningState = () => {
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["resources", "learning-state", resource.id] }),
      queryClient.invalidateQueries({ queryKey: ["learning", "next-action"] }),
      queryClient.invalidateQueries({ queryKey: ["paths"] })
    ]);
  };
  const openedMutation = useMutation({
    mutationFn: recordInteraction,
    onSuccess: refreshLearningState
  });
  const actionMutation = useMutation({
    mutationFn: recordInteraction,
    onSuccess: refreshLearningState
  });

  useEffect(() => {
    if (!Number.isFinite(resourceId) || openedResource.current === resource.id) return;
    openedResource.current = resource.id;
    openedMutation.mutate({ eventType: "opened" });
  // The mutation is intentionally excluded so one visible resource produces one opened event.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource.id, resourceId]);

  const state = stateQuery.data?.data;
  return (
    <section className="resource-learning-controls" aria-label="资源学习反馈">
      <div>
        <strong>{state?.completed ? "这份资源已完成" : "学完后由你确认"}</strong>
        <span>反馈只调整当前课程的资源组合，不会直接写入长期画像。</span>
      </div>
      <div className="resource-learning-actions">
        {!state?.started && !state?.completed ? (
          <button type="button" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ eventType: "started" })}>开始学习</button>
        ) : null}
        {!state?.completed ? (
          <button type="button" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ eventType: "completed" })}>完成学习</button>
        ) : null}
        {feedbackOptions.map((option) => (
          <button
            type="button"
            key={option.value}
            aria-pressed={state?.feedback === option.value}
            disabled={actionMutation.isPending}
            onClick={() => actionMutation.mutate({ eventType: "feedback", feedback: option.value })}
          >{option.label}</button>
        ))}
      </div>
      {actionMutation.isError || openedMutation.isError ? <p className="form-error">学习状态未保存，请重试。</p> : null}
    </section>
  );
}
