import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../../api/client";
import type { components } from "../../types/openapi.generated";

type Progress = components["schemas"]["TaskProgress"];

export function TaskEvidenceProgress({ taskId, resourceId, courseId, isQuiz }: {
  taskId: number; resourceId: number; courseId: string; isQuiz: boolean;
}) {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ["paths", "task-progress", taskId],
    queryFn: async () => (await apiClient.get<{ data: Progress }>(`/paths/tasks/${taskId}/progress`)).data.data
  });
  const practice = useMutation({
    mutationFn: async () => (await apiClient.post<{ data: { id: string } }>(`/paths/tasks/${taskId}/resources/${resourceId}/practice`)).data.data,
    onSuccess: (session) => navigate(`/app/practice?course_id=${courseId}&session_id=${session.id}`)
  });
  const state = query.data;
  if (query.isPending) return <section aria-label="任务证据状态">正在读取任务证据…</section>;
  if (query.isError) return <section aria-label="任务证据状态"><p role="alert">任务证据读取失败，请重试。</p></section>;
  return <section aria-label="任务证据状态">
    <p>用户标记：{state?.user_reported_completed ? "已学" : "未标记"} · 活动完成：{state?.activity_completed ? "已完成" : "未完成"}</p>
    <p>评估：{state?.assessment_passed ? "已通过" : "未通过"} · 掌握：{state?.mastered ? "已掌握" : "尚未掌握"}{state?.mastery_score != null ? `（${state.mastery_score}%）` : ""}</p>
    <p>活动反馈属于用户自述；评估与掌握来自服务端学习证据。</p>
    {state?.blocked_reasons?.map((reason) => <p key={reason}>{reason}</p>)}
    {isQuiz ? <button type="button" disabled={practice.isPending || !state || Boolean(state.blocked_reasons?.length)} onClick={() => practice.mutate()}>进入绑定测验</button> : null}
    {query.isError || practice.isError ? <p role="alert">任务证据或测验读取失败，请重试。</p> : null}
  </section>;
}
