import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { approvePath, getPathVersion, listPathDrafts } from "../../api/paths";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../course-space/courseLoopQueries";

export function PathDraftReview({ courseId, activePathId, currentReady }: {
  courseId: number; activePathId: string | null; currentReady: boolean;
}) {
  const client = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const drafts = useQuery({
    queryKey: courseLoopQueryKeys.pathDrafts(courseId),
    queryFn: () => listPathDrafts(courseId)
  });
  const detail = useQuery({
    queryKey: ["paths", "version", selectedId],
    queryFn: () => getPathVersion(selectedId!),
    enabled: selectedId !== null
  });
  const path = detail.data?.data.path;
  const rawBase = path?.plan_json.revision_of;
  const base = rawBase == null ? null : String(rawBase);
  const stale = base !== activePathId;
  const approval = useMutation({
    mutationFn: () => approvePath(path!.id, base === null ? null : Number(base)),
    onSuccess: async () => {
      setSelectedId(null);
      await invalidateCourseLearningLoop(client, courseId);
    },
    onError: () => { void invalidateCourseLearningLoop(client, courseId); }
  });
  if (drafts.isError) return <p role="alert">待确认计划读取失败。<button type="button" onClick={() => void drafts.refetch()}>重新读取</button></p>;
  if (!drafts.data?.data.length) return null;
  return (
    <section className="path-draft-review" aria-label="待确认计划">
      <h2>待确认计划</h2>
      <p>先查看任务安排，确认后启用。当前学习计划在确认前保持有效。</p>
      {drafts.data.data.map((draft) => (
        <button type="button" className="icon-text-button" key={draft.id} disabled={approval.isPending}
          aria-expanded={selectedId === draft.id}
          onClick={() => { setSelectedId(selectedId === draft.id ? null : draft.id); approval.reset(); }}>
          查看草稿：{draft.title} · 版本 {draft.id}
        </button>
      ))}
      {selectedId ? <div>
        {detail.isPending ? <p role="status">正在读取草稿…</p> : null}
        {detail.isError ? <p role="alert">草稿读取失败。<button type="button" onClick={() => void detail.refetch()}>重试</button></p> : null}
        {path ? <>
          <h3>{path.title}</h3><p>{path.goal}</p>
          <ol tabIndex={0} aria-label="草稿任务安排">{detail.data?.data.tasks.map((task) => <li key={task.id}><strong>{task.title}</strong><p>{task.reason}</p></li>)}</ol>
          {stale ? <p role="status">当前计划已变化，此草稿不能启用。请重新生成计划。</p> : null}
          {approval.isError ? <p role="alert">确认失败，当前计划可能已变化。已重新读取，请核对后重试。</p> : null}
          <button type="button" className="icon-text-button"
            disabled={!currentReady || stale || approval.isPending || path.status !== "draft" || !detail.data?.data.tasks.length}
            onClick={() => approval.mutate()}>{approval.isPending ? "正在确认…" : "确认并启用此计划"}</button>
        </> : null}
      </div> : null}
    </section>
  );
}
