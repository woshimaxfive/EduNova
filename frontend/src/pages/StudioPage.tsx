import { Sparkle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import { createIdempotencyKey, createResourceGenerationJob } from "../api/aiJobs";
import { getKnowledgePoints, listCourses } from "../api/courses";
import {
  getResourceQuality,
  listResources,
  type GeneratedResource,
  type ResourceDifficulty,
  type ResourceQualityScore,
  type ResourceType
} from "../api/resources";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { AiJobProgress } from "../components/feedback/AiJobProgress";
import { AgentTimeline } from "../components/evidence/AgentTimeline";
import { ResourceRenderer } from "../components/resources/ResourceRenderer";
import { StudioDock } from "../components/studio/StudioDock";
import { WorkspaceStateStrip } from "../components/states/WorkspaceStateStrip";
import { getWorkspaceStatePanels } from "../features/workspace/workflowState";
import { PageFrame } from "./PageFrame";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";

const resourceTypes: Array<{ type: ResourceType; label: string }> = [
  { type: "doc", label: "讲解" },
  { type: "quiz", label: "练习" },
  { type: "mindmap", label: "思维导图" },
  { type: "code", label: "代码实操" },
  { type: "slide", label: "PPT" },
  { type: "animation", label: "动画图解" }
];

const difficultyOptions: Array<{ value: ResourceDifficulty; label: string }> = [
  { value: "easy", label: "基础" },
  { value: "medium", label: "标准" },
  { value: "hard", label: "进阶" }
];

const qualityLabels: Record<string, string> = {
  source_match: "来源匹配",
  profile_fit: "画像贴合",
  fact_confidence: "事实置信",
  difficulty_fit: "难度贴合",
  completeness: "完整度"
};

function parseCourseId(value: string | null) {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function isLowEvidenceResource(resource: GeneratedResource) {
  return resource.review_status === "low_evidence" || resource.content_json.metadata?.generation_mode === "low_evidence_fallback";
}

export function StudioPage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const evidencePanels = getWorkspaceStatePanels().filter((panel) =>
    ["loading", "low_evidence", "local_preview"].includes(panel.kind)
  );
  const initialCourseId = parseCourseId(searchParams.get("course_id"));
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(initialCourseId);
  const [selectedKnowledgePointId, setSelectedKnowledgePointId] = useState<number | null>(null);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState<ResourceType[]>(["doc"]);
  const [learningGoal, setLearningGoal] = useState("");
  const [difficulty, setDifficulty] = useState<ResourceDifficulty>("medium");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [latestQualityScores, setLatestQualityScores] = useState<Record<string, ResourceQualityScore[]>>({});
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const resourceJob = getJob(resourceJobId);
  const isGenerating = Boolean(resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status));

  useEffect(() => {
    if (resourceJobId) return;
    const restored = jobs.find((job) => {
      const requestCourseId = Number(job.request.course_id);
      return job.workflow === "resource_generation"
        && ["queued", "running", "cancelling", "failed"].includes(job.status)
        && (initialCourseId === null || requestCourseId === initialCourseId);
    });
    if (!restored) return;
    const request = restored.request;
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (Number.isFinite(Number(request.course_id))) setSelectedCourseId(Number(request.course_id));
    if (request.knowledge_point_id !== null && Number.isFinite(Number(request.knowledge_point_id))) setSelectedKnowledgePointId(Number(request.knowledge_point_id));
    if (Array.isArray(request.resource_types)) setSelectedResourceTypes(request.resource_types as ResourceType[]);
    if (typeof request.learning_goal === "string") setLearningGoal(request.learning_goal);
    if (["easy", "medium", "hard"].includes(String(request.difficulty))) setDifficulty(request.difficulty as ResourceDifficulty);
    setResourceJobId(restored.job_id);
  }, [initialCourseId, jobs, resourceJobId]);

  const coursesQuery = useQuery({
    queryKey: ["courses", "studio"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const courses = useMemo(
    () => (Array.isArray(coursesQuery.data?.data) ? coursesQuery.data.data : []),
    [coursesQuery.data]
  );
  const effectiveCourseId = useMemo(() => {
    if (courses.length === 0) {
      return null;
    }

    const selectedExists = selectedCourseId !== null && courses.some((course) => Number.parseInt(course.id, 10) === selectedCourseId);
    if (selectedExists) {
      return selectedCourseId;
    }

    const initialExists = initialCourseId !== null && courses.some((course) => Number.parseInt(course.id, 10) === initialCourseId);
    return initialExists ? initialCourseId : Number.parseInt(courses[0].id, 10);
  }, [courses, initialCourseId, selectedCourseId]);
  const selectedCourse = courses.find((course) => Number.parseInt(course.id, 10) === effectiveCourseId) ?? null;

  const knowledgePointsQuery = useQuery({
    queryKey: ["courses", "knowledge-points", effectiveCourseId],
    queryFn: () => getKnowledgePoints(effectiveCourseId ?? 0),
    enabled: effectiveCourseId !== null,
    staleTime: 30_000
  });
  const knowledgePoints = useMemo(
    () => (Array.isArray(knowledgePointsQuery.data?.data) ? knowledgePointsQuery.data.data : []),
    [knowledgePointsQuery.data]
  );
  const effectiveKnowledgePointId = useMemo(() => {
    if (knowledgePoints.length === 0) {
      return null;
    }

    const selectedExists =
      selectedKnowledgePointId !== null && knowledgePoints.some((point) => Number.parseInt(point.id, 10) === selectedKnowledgePointId);
    return selectedExists ? selectedKnowledgePointId : Number.parseInt(knowledgePoints[0].id, 10);
  }, [knowledgePoints, selectedKnowledgePointId]);

  const resourceCourseId = effectiveCourseId ?? selectedCourseId;
  const resourcesQuery = useQuery({
    queryKey: resourceCourseId !== null ? courseLoopQueryKeys.resources(resourceCourseId) : ["resources", "all"],
    queryFn: () => listResources(resourceCourseId !== null ? { courseId: resourceCourseId } : undefined),
    staleTime: 10_000
  });
  const resources = useMemo(
    () => (Array.isArray(resourcesQuery.data?.data) ? resourcesQuery.data.data : []),
    [resourcesQuery.data]
  );

  const selectedResource = useMemo(
    () => resources.find((resource) => resource.id === selectedResourceId) ?? resources[0] ?? null,
    [resources, selectedResourceId]
  );
  const resourceQualityQuery = useQuery({
    queryKey: ["resources", "quality", selectedResource?.id],
    queryFn: () => getResourceQuality(Number.parseInt(selectedResource?.id ?? "0", 10)),
    enabled: selectedResource !== null,
    staleTime: 10_000
  });
  const selectedResourceQuality = selectedResource
    ? latestQualityScores[selectedResource.id] ?? resourceQualityQuery.data?.data ?? []
    : [];
  const selectedResourceTraceId = selectedResource?.agent_trace_id ?? selectedResource?.content_json.metadata?.agent_trace_id ?? null;
  const resourceTraceQuery = useQuery({
    queryKey: ["agents", "trace", selectedResourceTraceId],
    queryFn: () => getAgentTrace(selectedResourceTraceId ?? ""),
    enabled: Boolean(selectedResourceTraceId),
    staleTime: 30_000
  });
  const resourceTraceEvents = useMemo(
    () => resourceTraceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [resourceTraceQuery.data?.data.steps]
  );

  useEffect(() => {
    if (!resourceJob) return;
    if (resourceJob.status === "failed") {
      // Surface the terminal state delivered by the external job runtime.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFeedback(resourceJob.error_message ?? "资源生成失败，请稍后重试。");
      return;
    }
    if (resourceJob.status !== "completed") return;
    const resourceIds = Array.isArray(resourceJob.result.resource_ids)
      ? resourceJob.result.resource_ids.map(String)
      : [];
    setFeedback(resourceJob.warnings.join(" ") || "资源生成完成。");
    setLatestQualityScores({});
    if (resourceIds[0]) setSelectedResourceId(resourceIds[0]);
    if (effectiveCourseId !== null) void invalidateCourseLearningLoop(queryClient, effectiveCourseId);
  }, [effectiveCourseId, queryClient, resourceJob]);

  const generateMutation = useMutation({
    mutationFn: () => {
      if (effectiveCourseId === null) {
        throw new Error("missing course");
      }
      return createResourceGenerationJob(
        {
          course_id: effectiveCourseId,
          knowledge_point_id: effectiveKnowledgePointId,
          resource_types: selectedResourceTypes,
          learning_goal: learningGoal,
          difficulty
        },
        createIdempotencyKey("studio-resource")
      );
    },
    onSuccess: (job) => {
      setResourceJobId(job.job_id);
      trackJob(job);
    },
    onError: () => {
      setFeedback("资源生成失败，请稍后重试。");
    }
  });

  function toggleResourceType(type: ResourceType) {
    setSelectedResourceTypes((current) => {
      if (current.includes(type)) {
        return current.length === 1 ? current : current.filter((item) => item !== type);
      }
      return [...current, type];
    });
  }

  function handleCourseChange(value: string) {
    setSelectedCourseId(value ? Number.parseInt(value, 10) : null);
    setSelectedKnowledgePointId(null);
    setLatestQualityScores({});
  }

  function handleGenerate() {
    if (effectiveCourseId === null || generateMutation.isPending || isGenerating) {
      return;
    }
    generateMutation.mutate();
  }

  const canGenerate = effectiveCourseId !== null && selectedResourceTypes.length > 0 && !generateMutation.isPending && !isGenerating;
  const selectedKnowledgePoint = knowledgePoints.find((point) => Number.parseInt(point.id, 10) === effectiveKnowledgePointId) ?? null;
  const selectedKnowledgePointTitle = selectedKnowledgePoint?.title ?? "整门课程";
  const selectedResourceTypeSummary = selectedResourceTypes
    .map((type) => resourceTypes.find((item) => item.type === type)?.label ?? type)
    .join("、");
  const hasResourceResult = selectedResource !== null;

  const studioDock = (
    <StudioDock
      outputs={resources}
      selectedResourceId={selectedResource?.id ?? null}
      onGenerate={handleGenerate}
      onSelectResource={setSelectedResourceId}
      showGenerateAction={false}
    />
  );

  const resourceResultSections = selectedResource ? (
    <>
      <section className="student-panel resource-detail-panel" role="region" aria-label="资源完整内容">
        <div className="student-panel-heading">
          <div>
            <h2>资源内容</h2>
          </div>
        </div>
        {isLowEvidenceResource(selectedResource) ? (
          <InlineFeedback
            message="资料依据不足，这份资源是低依据草稿，请补充课程资料后重新生成。"
            tone="warning"
            className="library-inline-feedback"
          />
        ) : null}
        <article className="resource-reader">
          <strong>{selectedResource.title}</strong>
          <ResourceRenderer resource={selectedResource} />
        </article>
      </section>

      <section className="student-panel generation-queue" role="region" aria-label="资源质量">
        <div className="student-panel-heading">
          <div>
            <h2>资源质量</h2>
          </div>
        </div>
        {selectedResourceQuality.length > 0 ? (
          selectedResourceQuality.map((score) => (
            <article className="queue-row" key={score.id}>
              <span>
                <strong>{qualityLabels[score.score_name] ?? score.score_name}</strong>
                <small>{score.rationale ?? "已记录质量分"}</small>
              </span>
              <em>{score.score_value.toFixed(2)}</em>
            </article>
          ))
        ) : (
          <p className="empty-inline-note">资源质量分会在生成后显示。</p>
        )}
      </section>

      <section className="student-panel generation-queue" role="region" aria-label="引用来源">
        <div className="student-panel-heading">
          <div>
            <h2>引用来源</h2>
          </div>
        </div>
        {selectedResource.citation_json.length > 0 ? (
          selectedResource.citation_json.map((citation, index) => (
            <article className="queue-row" key={`${citation.chunk_id ?? index}-${citation.section_title ?? "citation"}`}>
              <span>
                <strong>{citation.section_title ?? "课程引用"}</strong>
                <small>{citation.source_title ?? "课程资料"}</small>
              </span>
            </article>
          ))
        ) : (
          <p className="empty-inline-note">当前资源没有可展示引用。</p>
        )}
      </section>

      <section className="student-panel generation-queue" role="region" aria-label="资源生成链路">
        <div className="student-panel-heading">
          <div>
            <h2>ResourceGenerationGraph</h2>
          </div>
        </div>
        {resourceTraceQuery.isError ? (
          <InlineFeedback message="资源生成轨迹读取失败，请稍后重试。" tone="warning" className="library-inline-feedback" />
        ) : resourceTraceQuery.isPending && resourceTraceQuery.fetchStatus !== "idle" ? (
          <p className="empty-inline-note">正在读取资源生成链路。</p>
        ) : resourceTraceEvents.length > 0 ? (
          <AgentTimeline events={resourceTraceEvents} />
        ) : (
          <p className="empty-inline-note">
            {selectedResourceTraceId ? "当前资源 trace 暂无可展示步骤。" : "生成后会展示 Profile、Retriever、Diagnosis、Resource、Review、Persist 全链路。"}
          </p>
        )}
      </section>
    </>
  ) : null;

  return (
    <PageFrame title="资源工坊">
      {hasResourceResult ? (
        <div className="studio-results-first">
          <section className="student-panel studio-result-summary" role="region" aria-label="资源生成摘要">
            <div className="studio-result-summary-copy">
              <span>已生成资源</span>
              <strong>{selectedResource.title}</strong>
            </div>
            <dl className="studio-result-meta" aria-label="当前生成条件">
              <div>
                <dt>课程</dt>
                <dd>{selectedCourse?.title ?? "暂无课程"}</dd>
              </div>
              <div>
                <dt>知识点</dt>
                <dd>{selectedKnowledgePointTitle}</dd>
              </div>
              <div>
                <dt>类型</dt>
                <dd>{selectedResourceTypeSummary}</dd>
              </div>
            </dl>
            <button className="primary-action" type="button" onClick={handleGenerate} disabled={!canGenerate}>
              <Sparkle size={18} weight="fill" aria-hidden="true" />
              <span>{generateMutation.isPending || isGenerating ? "生成中" : "重新生成"}</span>
            </button>
            <InlineFeedback message={feedback} tone="warning" className="library-inline-feedback" />
            {resourceJob ? (
              <AiJobProgress
                job={resourceJob}
                onCancel={() => void cancelJob(resourceJob.job_id)}
                onRetry={() => void retryJob(resourceJob.job_id).then((job) => setResourceJobId(job.job_id))}
              />
            ) : null}
            {coursesQuery.isError || resourcesQuery.isError ? (
              <InlineFeedback message="资源工坊数据读取失败，请稍后重试。" tone="warning" className="library-inline-feedback" />
            ) : null}
          </section>

          {studioDock}
          {resourceResultSections}
        </div>
      ) : null}

      <section
        className={hasResourceResult ? "student-panel studio-workbench studio-workbench-secondary" : "student-panel studio-workbench"}
        role="region"
        aria-label="资源生成工作台"
      >
        <div className="student-panel-heading">
          <div>
            <h2>{hasResourceResult ? "调整生成设置" : "选择课程和知识点，生成资源"}</h2>
          </div>
          <button className="primary-action" type="button" onClick={handleGenerate} disabled={!canGenerate}>
            <Sparkle size={18} weight="fill" aria-hidden="true" />
            <span>{generateMutation.isPending || isGenerating ? "生成中" : "生成资源"}</span>
          </button>
        </div>

        {!hasResourceResult && resourceJob ? (
          <AiJobProgress
            job={resourceJob}
            onCancel={() => void cancelJob(resourceJob.job_id)}
            onRetry={() => void retryJob(resourceJob.job_id).then((job) => setResourceJobId(job.job_id))}
          />
        ) : null}

        <div className="studio-control-grid">
          <label>
            <span>课程</span>
            <select
              value={effectiveCourseId ?? ""}
              onChange={(event) => handleCourseChange(event.target.value)}
              disabled={courses.length === 0}
            >
              {courses.length > 0 ? (
                courses.map((course) => (
                  <option key={course.id} value={Number.parseInt(course.id, 10)}>
                    {course.title}
                  </option>
                ))
              ) : (
                <option value="">还没有可生成资源的课程</option>
              )}
            </select>
          </label>
          <label>
            <span>知识点</span>
            <select
              value={effectiveKnowledgePointId ?? ""}
              onChange={(event) => setSelectedKnowledgePointId(event.target.value ? Number.parseInt(event.target.value, 10) : null)}
              disabled={knowledgePoints.length === 0}
            >
              {knowledgePoints.length > 0 ? (
                knowledgePoints.map((point) => (
                  <option key={point.id} value={Number.parseInt(point.id, 10)}>
                    {point.title}
                  </option>
                ))
              ) : (
                <option value="">按整门课程生成</option>
              )}
            </select>
          </label>
          <label>
            <span>生成目标</span>
            <input
              aria-label="生成目标"
              value={learningGoal}
              onChange={(event) => setLearningGoal(event.target.value)}
              placeholder="例如：期末前掌握搜索题"
            />
          </label>
          <label>
            <span>难度</span>
            <select value={difficulty} onChange={(event) => setDifficulty(event.target.value as ResourceDifficulty)}>
              {difficultyOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="resource-type-row" aria-label="资源类型">
            {resourceTypes.map((item) => (
              <button
                className={selectedResourceTypes.includes(item.type) ? "active" : ""}
                key={item.type}
                type="button"
                aria-pressed={selectedResourceTypes.includes(item.type)}
                onClick={() => toggleResourceType(item.type)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {!hasResourceResult ? <InlineFeedback message={feedback} tone="warning" className="library-inline-feedback" /> : null}
        {!hasResourceResult && (coursesQuery.isError || resourcesQuery.isError) ? (
          <InlineFeedback message="资源工坊数据读取失败，请稍后重试。" tone="warning" className="library-inline-feedback" />
        ) : null}

        {!hasResourceResult ? <WorkspaceStateStrip panels={evidencePanels} /> : null}

        {!hasResourceResult ? (
          <section className="generation-queue" role="region" aria-label="生成队列">
            {selectedCourse ? (
              <article className="queue-row">
                <span className="queue-row-icon" aria-hidden="true">
                  <Sparkle size={19} weight="duotone" />
                </span>
                <span>
                  <strong>{selectedCourse.title}</strong>
                  <small>{selectedResourceTypes.length} 类资源 · {knowledgePoints.length > 0 ? "知识点生成" : "整课生成"}</small>
                </span>
              </article>
            ) : (
              <p className="empty-inline-note">还没有可生成资源的课程</p>
            )}
          </section>
        ) : null}
      </section>

      {!hasResourceResult ? studioDock : null}
    </PageFrame>
  );
}
