import { BookOpen, CheckCircle, LinkSimple, MagnifyingGlass, Sparkle, X } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { getAgentTrace, mapAgentTraceStepToEvent } from "../../api/agents";
import type { AiJob } from "../../api/aiJobs";
import { listCourses } from "../../api/courses";
import type { TutorCitation } from "../../api/tutor";
import type { HomeAnswerPanel, HomeMessage, LibraryMaterial } from "../../features/home/homeLearningModel";
import { AgentTimeline } from "../evidence/AgentTimeline";
import { AiJobProgress } from "../feedback/AiJobProgress";
import { InlineFeedback, type FeedbackTone } from "../feedback/InlineFeedback";
import { ModalFrame } from "../primitives/Dialog";

export function HomeResourceCourseDialog({ onClose, onSelect }: { onClose: () => void; onSelect: (courseId: number) => void }) {
  const coursesQuery = useQuery({ queryKey: ["courses", "resource-target"], queryFn: () => listCourses(), staleTime: 30_000 });
  const courses = coursesQuery.data?.data ?? [];
  return (
    <ModalFrame title="选择资源课程" layerClassName="course-dialog-backdrop" onClose={onClose}>
      <section className="course-dialog home-resource-course-dialog" aria-label="选择资源保存课程">
        <div className="dialog-copy"><h2>保存到哪门课程？</h2><p>选择课程后，系统会结合该课程的资料、知识点和学习进度生成资源。</p></div>
        {coursesQuery.isPending ? <span>正在读取课程...</span> : null}
        {coursesQuery.isError ? <span>课程列表读取失败，请关闭后重试。</span> : null}
        <div className="home-resource-course-list">
          {courses.map((course) => (
            <button type="button" key={course.id} onClick={() => onSelect(Number(course.id))}>
              <BookOpen size={18} weight="duotone" aria-hidden="true" />
              <span><strong>{course.title}</strong><small>{course.subject || "未标注学科"}</small></span>
            </button>
          ))}
        </div>
      </section>
    </ModalFrame>
  );
}

type HomeAnswerInsightsProps = {
  message: HomeMessage;
  activePanel: HomeAnswerPanel;
  expandedAnswerId: string | null;
  selectedMaterialCount: number;
  warnings: string[];
  onTogglePanel: (panel: HomeAnswerPanel, messageId: string | null) => void;
};

export function HomeAnswerInsights({
  message,
  activePanel,
  expandedAnswerId,
  selectedMaterialCount,
  warnings,
  onTogglePanel
}: HomeAnswerInsightsProps) {
  const messageId = message.id;
  const isExpanded = expandedAnswerId === messageId;
  const traceQuery = useQuery({
    queryKey: ["agents", "trace", message.trace_id],
    queryFn: () => getAgentTrace(message.trace_id ?? ""),
    enabled: Boolean(message.trace_id) && isExpanded && (activePanel === "why" || activePanel === "trace"),
    staleTime: 10_000
  });
  const personalizationCount = useMemo(
    () => traceQuery.data?.data.summary?.personalization_factors?.length ?? 0,
    [traceQuery.data?.data.summary?.personalization_factors]
  );
  const traceEvents = useMemo(
    () => traceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [traceQuery.data?.data.steps]
  );
  const handleInsightClick = (panel: HomeAnswerPanel) => {
    const shouldCollapse = isExpanded && activePanel === panel;

    onTogglePanel(panel, shouldCollapse ? null : messageId);
  };
  const citations = message.citation_json ?? [];
  const hasCitations = citations.length > 0;
  const sourceText = hasCitations
    ? `本次回答返回 ${citations.length} 条真实来源。`
    : selectedMaterialCount > 0
      ? `系统已检索 ${selectedMaterialCount} 份已选资料，但没有返回可展示来源。`
      : "系统没有找到需要展示的资料或网页来源。";

  return (
    <section className="home-answer-insights" aria-label="回答附加信息">
      <div className="answer-insight-tabs" aria-label="回答展开入口">
        <button
          className={isExpanded && activePanel === "why" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "why"}
          aria-pressed={isExpanded && activePanel === "why"}
          onClick={() => handleInsightClick("why")}
        >
          <Sparkle size={16} weight="duotone" aria-hidden="true" />
          <span>为什么这样回答</span>
        </button>
        <button
          className={isExpanded && activePanel === "sources" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "sources"}
          aria-pressed={isExpanded && activePanel === "sources"}
          onClick={() => handleInsightClick("sources")}
        >
          <LinkSimple size={16} weight="duotone" aria-hidden="true" />
          <span>来源</span>
        </button>
        {message.trace_id ? (
          <button
            className={isExpanded && activePanel === "trace" ? "active" : ""}
            type="button"
            aria-expanded={isExpanded && activePanel === "trace"}
            aria-pressed={isExpanded && activePanel === "trace"}
            onClick={() => handleInsightClick("trace")}
          >
            <Sparkle size={16} weight="duotone" aria-hidden="true" />
            <span>协作轨迹</span>
          </button>
        ) : null}
      </div>

      {isExpanded ? (
        <div className="answer-insight-panel" role="region" aria-label="回答展开详情">
          {activePanel === "sources" ? (
            <>
              <span className="insight-mark">
                <CheckCircle size={16} weight="fill" aria-hidden="true" />
                来源
              </span>
              <p>{sourceText}</p>
              {warnings.length > 0 ? (
                <ul className="insight-warning-list" aria-label="工具提示">
                  {warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
              {hasCitations ? (
                <ul className="insight-source-list">
                  {citations.map((citation, index) => (
                    <li key={`${citation.source_type ?? "source"}-${citation.url ?? citation.source_title ?? citation.title ?? index}`}>
                      <div>
                        <strong>{citation.title ?? citation.source_title ?? `来源 ${index + 1}`}</strong>
                        <span>{sourceTypeLabel(citation.source_type)}{citation.access_scope === "external_fallback" ? " · 境外补充" : citation.access_scope === "mainland_preferred" ? " · 国内优先来源" : ""}</span>
                      </div>
                      {citation.snippet || citation.content ? <p>{citation.snippet ?? citation.content}</p> : null}
                      {citation.url ? (
                        <a href={citation.url} target="_blank" rel="noreferrer">
                          {citation.url}
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
          {activePanel === "why" ? (
            <>
              <span className="insight-mark"><Sparkle size={16} weight="fill" aria-hidden="true" />为什么这样回答</span>
              <p>
                {personalizationCount
                  ? `本次讲解依据课程上下文，并使用 ${personalizationCount} 项可信学习因素调整讲解深度、案例和下一步；这些因素不会改变事实或引用。`
                  : "本次主要依据问题、会话上下文和可验证来源组织回答，没有使用低可信画像改变内容。"}
              </p>
            </>
          ) : null}
          {activePanel === "trace" ? (
            <>
              <span className="insight-mark"><Sparkle size={16} weight="fill" aria-hidden="true" />智能体协作轨迹</span>
              {traceQuery.isPending ? <p>正在读取协作轨迹。</p> : null}
              {traceQuery.isError ? <p>协作轨迹读取失败，请稍后重试。</p> : null}
              {traceEvents.length > 0 ? <AgentTimeline events={traceEvents} summary={traceQuery.data?.data.summary} /> : null}
              {!traceQuery.isPending && !traceQuery.isError && traceEvents.length === 0 ? <p>当前协作轨迹暂无可展示步骤。</p> : null}
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function sourceTypeLabel(sourceType: TutorCitation["source_type"]) {
  if (sourceType === "web") {
    return "外部补充";
  }
  if (sourceType === "history") {
    return "历史对话";
  }
  if (sourceType === "material") {
    return "资料";
  }
  if (sourceType === "course") {
    return "课程";
  }
  return "来源";
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

type CourseGenerationDialogWithNoticeProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onCreate: (courseTitle: string) => void;
  isCreatingCourse: boolean;
  initialCourseTitle?: string;
  job?: AiJob;
  onCancelJob: () => void;
  onRetryJob: () => void;
  feedback: { message: string; tone: FeedbackTone } | null;
};

export function CourseGenerationDialog({
  materials,
  selectedMaterialIds,
  onToggleMaterial,
  onClose,
  onCreate,
  isCreatingCourse,
  initialCourseTitle,
  job,
  onCancelJob,
  onRetryJob,
  feedback
}: CourseGenerationDialogWithNoticeProps) {
  const selectedCount = selectedMaterialIds.length;
  const [courseTitle, setCourseTitle] = useState(initialCourseTitle || "我的资料课程");

  return (
    <ModalFrame title="从资料生成课程" layerClassName="course-dialog-backdrop" onClose={onClose} dismissible={!isCreatingCourse}>
      <section className="course-dialog" aria-labelledby="course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="course-dialog-title">从资料生成课程</h2>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" value={courseTitle} onChange={(event) => setCourseTitle(event.target.value)} />
        </label>
        <MaterialFileList materials={materials} selectedMaterialIds={selectedMaterialIds} onToggleMaterial={onToggleMaterial} />
        <div className="dialog-selection-summary">
          <strong>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "先选择要生成课程的资料"}</strong>
          <small>只建立关联，不移动原文件。</small>
        </div>
        <InlineFeedback message={feedback?.message ?? null} tone={feedback?.tone} className="dialog-inline-feedback" />
        {job ? <AiJobProgress job={job} onCancel={onCancelJob} onRetry={onRetryJob} /> : null}
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0 || isCreatingCourse}
          onClick={() => onCreate(courseTitle)}
        >
          {isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </ModalFrame>
  );
}

type MaterialLibraryDrawerProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onOpenCourseGeneration: () => void;
  onConfirm: () => void;
  allowClear: boolean;
  feedback: { message: string; tone: FeedbackTone } | null;
};

export function MaterialLibraryDrawer({ materials, selectedMaterialIds, onToggleMaterial, onOpenCourseGeneration, onConfirm, allowClear, feedback, onClose }: MaterialLibraryDrawerProps) {
  const selectedCount = selectedMaterialIds.length;
  const [searchTerm, setSearchTerm] = useState("");
  const visibleMaterials = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    if (!normalizedSearch) {
      return materials;
    }

    return materials.filter((material) =>
      `${material.title} ${material.type} ${material.detail}`.toLowerCase().includes(normalizedSearch)
    );
  }, [materials, searchTerm]);

  return (
    <ModalFrame title="资料库" layerClassName="course-dialog-backdrop" onClose={onClose}>
      <section className="material-drawer" aria-labelledby="library-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭资料库" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="library-dialog-title">资料库</h2>
        </div>
        <div className="file-library-toolbar">
          <label className="file-search-field">
            <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
            <input aria-label="搜索资料" placeholder="搜索资料" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
          </label>
          <button type="button" onClick={onOpenCourseGeneration}>
            <Sparkle size={17} weight="duotone" aria-hidden="true" />
            <span>生成课程</span>
          </button>
        </div>
        <MaterialFileList
          materials={visibleMaterials}
          selectedMaterialIds={selectedMaterialIds}
          onToggleMaterial={onToggleMaterial}
          emptyText={materials.length === 0 ? undefined : "没有匹配的资料。"}
        />
        <div className="library-dialog-footer">
          <span>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "当前未选择资料"}</span>
          <InlineFeedback message={feedback?.message ?? null} tone={feedback?.tone} />
          <button
            className="dialog-primary-button"
            type="button"
            disabled={selectedCount === 0 && !allowClear}
            onClick={onConfirm}
          >
            {selectedCount > 0 || !allowClear ? "作为本次对话参考" : "清空对话参考"}
          </button>
        </div>
      </section>
    </ModalFrame>
  );
}

type MaterialFileListProps = {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  emptyText?: string;
};

function MaterialFileList({ materials, selectedMaterialIds, onToggleMaterial, emptyText = "资料库还是空的，先上传一份课件或试卷。" }: MaterialFileListProps) {
  return (
    <div className="material-file-list" role="list" aria-label="资料库文件列表">
      <div className="material-file-header" aria-hidden="true">
        <span>名称</span>
        <span>修改时间</span>
        <span>大小</span>
      </div>
      {materials.length === 0 ? <p className="material-file-empty">{emptyText}</p> : null}
      {materials.map((material) => {
        const isSelected = selectedMaterialIds.includes(material.id);
        const unavailable = Boolean(material.ingestion_status && material.ingestion_status !== "confirmed");

        return (
          <button
            className={isSelected ? "material-file-row selected" : "material-file-row"}
            key={material.id}
            type="button"
            aria-pressed={isSelected}
            disabled={unavailable}
            onClick={() => onToggleMaterial(material.id)}
          >
            <span className="material-file-type">{material.type}</span>
            <span className="material-file-main">
              <strong>{material.title}</strong>
              <small>{unavailable ? "请先到资料库检查并确认目录" : material.detail}</small>
            </span>
            <span className="material-file-meta">{material.modified}</span>
            <span className="material-file-meta">{material.size}</span>
            {isSelected ? <CheckCircle size={18} weight="duotone" aria-hidden="true" /> : null}
          </button>
        );
      })}
    </div>
  );
}
