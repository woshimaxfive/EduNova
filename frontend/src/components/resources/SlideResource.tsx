import { CaretLeft, CaretRight, DownloadSimple, Presentation, SpinnerGap } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { downloadExportJob } from "../../api/exports";
import {
  createResourceExportJob,
  listResourceExportJobs,
  type GeneratedResource,
  type ResourceSlideArtifact
} from "../../api/resources";

type SlideResourceProps = {
  artifact: ResourceSlideArtifact;
  resource: GeneratedResource;
};

export function SlideResource({ artifact, resource }: SlideResourceProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [feedback, setFeedback] = useState<string | null>(null);
  const autoQueuedRef = useRef(false);
  const queryClient = useQueryClient();
  const resourceId = Number.parseInt(resource.id, 10);
  const jobsQuery = useQuery({
    queryKey: ["resources", "exports", resource.id],
    queryFn: () => listResourceExportJobs(resourceId),
    enabled: Number.isFinite(resourceId),
    refetchInterval: (query) => {
      const jobs = query.state.data?.data ?? [];
      return jobs.some((job) => job.status === "queued" || job.status === "running") ? 1500 : false;
    }
  });
  const jobs = jobsQuery.data?.data ?? [];
  const latestJob = jobs[0] ?? null;
  const slide = artifact.slides[activeIndex];

  const createMutation = useMutation({
    mutationFn: () => createResourceExportJob(resourceId),
    onSuccess: () => {
      setFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["resources", "exports", resource.id] });
    },
    onError: () => setFeedback("PPTX 生成任务创建失败，请稍后重试。")
  });

  useEffect(() => {
    if (!jobsQuery.isSuccess || jobs.length > 0 || autoQueuedRef.current || !Number.isFinite(resourceId)) {
      return;
    }
    autoQueuedRef.current = true;
    createMutation.mutate();
  }, [createMutation, jobs.length, jobsQuery.isSuccess, resourceId]);

  const statusLabel = useMemo(() => {
    if (createMutation.isPending || latestJob?.status === "queued") return "正在排队";
    if (latestJob?.status === "running") return "正在生成 PPTX";
    if (latestJob?.status === "completed") return "PPTX 已就绪";
    if (latestJob?.status === "failed") return "PPTX 生成失败";
    return "正在准备 PPTX";
  }, [createMutation.isPending, latestJob?.status]);

  async function downloadPptx() {
    if (!latestJob || latestJob.status !== "completed") {
      createMutation.mutate();
      return;
    }
    try {
      const response = await downloadExportJob(latestJob.job_id);
      const url = URL.createObjectURL(response);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = latestJob.filename ?? `${resource.title}.pptx`;
      anchor.click();
      URL.revokeObjectURL(url);
      setFeedback(null);
    } catch {
      setFeedback("PPTX 下载失败，请稍后重试。")
    }
  }

  return (
    <div className="resource-slide-shell">
      <aside className="resource-slide-thumbnails" aria-label="PPT 页面">
        {artifact.slides.map((item, index) => (
          <button
            className={index === activeIndex ? "active" : ""}
            key={item.id}
            type="button"
            aria-label={`查看第 ${index + 1} 页 ${item.title}`}
            aria-pressed={index === activeIndex}
            onClick={() => setActiveIndex(index)}
          >
            <span>{index + 1}</span>
            <strong>{item.title}</strong>
          </button>
        ))}
      </aside>
      <div className="resource-slide-main">
        <div className="resource-slide-toolbar">
          <span><Presentation size={17} aria-hidden="true" />{statusLabel}</span>
          <button type="button" onClick={() => void downloadPptx()} disabled={createMutation.isPending || latestJob?.status === "running"}>
            {createMutation.isPending || latestJob?.status === "running" || latestJob?.status === "queued" ? (
              <SpinnerGap className="spin" size={17} aria-hidden="true" />
            ) : (
              <DownloadSimple size={17} aria-hidden="true" />
            )}
            <span>{latestJob?.status === "completed" ? "下载 PPTX" : latestJob?.status === "failed" ? "重新生成" : "生成 PPTX"}</span>
          </button>
        </div>
        <article className="resource-slide-canvas" aria-label={`PPT 第 ${activeIndex + 1} 页`}>
          <span>EduNova · {activeIndex + 1}</span>
          <h3>{slide.title}</h3>
          <ul>{slide.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>
          <p>{slide.speaker_notes}</p>
        </article>
        <div className="resource-slide-navigation">
          <button type="button" aria-label="上一页 PPT" disabled={activeIndex === 0} onClick={() => setActiveIndex((current) => current - 1)}>
            <CaretLeft size={18} aria-hidden="true" />
          </button>
          <span>{activeIndex + 1} / {artifact.slides.length}</span>
          <button
            type="button"
            aria-label="下一页 PPT"
            disabled={activeIndex === artifact.slides.length - 1}
            onClick={() => setActiveIndex((current) => current + 1)}
          >
            <CaretRight size={18} aria-hidden="true" />
          </button>
        </div>
        {feedback ?? latestJob?.error_message ? <p className="resource-export-feedback">{feedback ?? latestJob?.error_message}</p> : null}
      </div>
    </div>
  );
}
