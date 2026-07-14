import { ArrowClockwise, X } from "@phosphor-icons/react";
import { type KeyboardEvent } from "react";

import { type AgentTraceEvent } from "../../types/api";
import { type AiJob } from "../../api/aiJobs";
import { type ApiCourseKnowledgePoint, type ApiCourseSummary } from "../../api/courses";
import {
  type GeneratedResource,
  type ResourceDifficulty,
  type ResourceQualityScore,
  type ResourceType
} from "../../api/resources";
import { AgentTimeline } from "../evidence/AgentTimeline";
import { AiJobProgress } from "../feedback/AiJobProgress";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { resourceTypeMeta } from "./studioResourceMeta";

export type StudioDrawerMode = "generate" | "details" | null;
export type StudioDetailTab = "quality" | "sources" | "trace";

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
  completeness: "完整度",
  authenticity: "真实性",
  personalization: "个性化",
  diversity: "差异性",
  pedagogical_utility: "教学可用性",
  type_correctness: "类型正确性"
};

type StudioDrawerProps = {
  mode: StudioDrawerMode;
  detailTab: StudioDetailTab;
  courses: ApiCourseSummary[];
  courseId: number | null;
  knowledgePoints: ApiCourseKnowledgePoint[];
  knowledgePointId: number | null;
  selectedTypes: ResourceType[];
  learningGoal: string;
  difficulty: ResourceDifficulty;
  resource: GeneratedResource | null;
  qualityScores: ResourceQualityScore[];
  traceEvents: AgentTraceEvent[];
  traceLoading: boolean;
  traceError: boolean;
  traceId: string | null;
  job: AiJob | undefined;
  feedback: string | null;
  canGenerate: boolean;
  isGenerating: boolean;
  onClose: () => void;
  onDetailTabChange: (tab: StudioDetailTab) => void;
  onCourseChange: (courseId: number | null) => void;
  onKnowledgePointChange: (knowledgePointId: number | null) => void;
  onToggleType: (type: ResourceType) => void;
  onLearningGoalChange: (value: string) => void;
  onDifficultyChange: (difficulty: ResourceDifficulty) => void;
  onGenerate: () => void;
  onCancelJob: () => void;
  onRetryJob: () => void;
};

export function StudioDrawer(props: StudioDrawerProps) {
  if (!props.mode) return null;
  const title = props.mode === "generate" ? "生成设置" : "成果详情";

  function keepKeyboardInside(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") props.onClose();
  }

  return (
    <div className="studio-drawer-layer" role="presentation" data-testid="studio-drawer-layer" onMouseDown={(event) => {
      if (event.target === event.currentTarget) props.onClose();
    }}>
      <aside
        className="studio-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={keepKeyboardInside}
      >
        <header className="studio-drawer-header">
          <div>
            <span>资源工坊</span>
            <h2>{title}</h2>
          </div>
          <button type="button" aria-label={`关闭${title}`} onClick={props.onClose}>
            <X size={19} weight="bold" aria-hidden="true" />
          </button>
        </header>

        {props.mode === "generate" ? <GeneratePanel {...props} /> : <DetailsPanel {...props} />}
      </aside>
    </div>
  );
}

function GeneratePanel(props: StudioDrawerProps) {
  const selectedLabels = props.selectedTypes.map((type) => resourceTypeMeta[type].label).join("、");
  return (
    <>
      <div className="studio-drawer-scroll studio-generate-panel">
        <label className="studio-drawer-field">
          <span>课程</span>
          <select
            aria-label="生成课程"
            value={props.courseId ?? ""}
            disabled={props.courses.length === 0}
            onChange={(event) => props.onCourseChange(event.target.value ? Number.parseInt(event.target.value, 10) : null)}
          >
            {props.courses.length > 0 ? props.courses.map((course) => (
              <option key={course.id} value={course.id}>{course.title}</option>
            )) : <option value="">还没有课程</option>}
          </select>
        </label>

        <label className="studio-drawer-field">
          <span>知识点</span>
          <select
            aria-label="生成知识点"
            value={props.knowledgePointId ?? ""}
            disabled={props.knowledgePoints.length === 0}
            onChange={(event) => props.onKnowledgePointChange(event.target.value ? Number.parseInt(event.target.value, 10) : null)}
          >
            {props.knowledgePoints.length > 0 ? props.knowledgePoints.map((point) => (
              <option key={point.id} value={point.id}>{point.title}</option>
            )) : <option value="">按整门课程生成</option>}
          </select>
        </label>

        <label className="studio-drawer-field">
          <span>生成目标</span>
          <input
            aria-label="生成目标"
            value={props.learningGoal}
            onChange={(event) => props.onLearningGoalChange(event.target.value)}
            placeholder="例如：期末前掌握搜索题"
          />
        </label>

        <fieldset className="studio-difficulty-control">
          <legend>难度</legend>
          <div>
            {difficultyOptions.map((option) => (
              <button
                type="button"
                key={option.value}
                className={props.difficulty === option.value ? "active" : ""}
                aria-pressed={props.difficulty === option.value}
                onClick={() => props.onDifficultyChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="studio-type-grid">
          <legend>资源类型</legend>
          <div>
            {Object.entries(resourceTypeMeta).map(([type, meta]) => {
              const resourceType = type as ResourceType;
              const checked = props.selectedTypes.includes(resourceType);
              return (
                <label className={checked ? "active" : ""} key={type}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => props.onToggleType(resourceType)}
                  />
                  <meta.Icon size={19} weight="duotone" />
                  <span>{meta.label}</span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {props.job ? (
          <AiJobProgress job={props.job} onCancel={props.onCancelJob} onRetry={props.onRetryJob} />
        ) : null}
        <InlineFeedback message={props.feedback} tone="warning" className="studio-drawer-feedback" />
      </div>

      <footer className="studio-drawer-footer">
        <p>{props.selectedTypes.length} 类资源 · {selectedLabels || "至少选择一类"}</p>
        <button className="primary-action" type="button" disabled={!props.canGenerate} onClick={props.onGenerate}>
          {props.isGenerating ? <ArrowClockwise className="spinning" size={17} /> : null}
          <span>{props.isGenerating ? "生成中" : "开始生成"}</span>
        </button>
      </footer>
    </>
  );
}

function DetailsPanel(props: StudioDrawerProps) {
  return (
    <div className="studio-drawer-scroll studio-details-panel">
      <div className="studio-detail-tabs" role="tablist" aria-label="成果详情分类">
        {([
          ["quality", "质量"],
          ["sources", "来源"],
          ["trace", "协作轨迹"]
        ] as const).map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={props.detailTab === tab}
            className={props.detailTab === tab ? "active" : ""}
            onClick={() => props.onDetailTabChange(tab)}
          >
            {label}
          </button>
        ))}
      </div>

      {props.detailTab === "quality" ? (
        <section role="tabpanel" aria-label="资源质量">
          {props.resource?.content_json.quality ? (
            <article className="studio-quality-row">
              <div><strong>内容门禁</strong><span>{props.resource.content_json.quality.status === "passed" ? "通过" : "未通过"}</span></div>
              <p>
                协议 {props.resource.content_json.quality.prompt_version ?? "legacy"}
                {props.resource.content_json.quality.code_verification?.status === "passed" ? " · 代码已实际运行验证" : ""}
              </p>
            </article>
          ) : null}
          {props.qualityScores.length > 0 ? props.qualityScores.map((score) => (
            <article className="studio-quality-row" key={score.id}>
              <div><strong>{qualityLabels[score.score_name] ?? score.score_name}</strong><span>{score.score_value.toFixed(2)}</span></div>
              <p>{score.rationale ?? "已记录质量分。"}</p>
            </article>
          )) : <p className="studio-drawer-empty">当前资源没有可展示质量分。</p>}
        </section>
      ) : null}

      {props.detailTab === "sources" ? (
        <section role="tabpanel" aria-label="引用来源">
          {props.resource?.citation_json.length ? props.resource.citation_json.map((citation, index) => (
            <article className="studio-source-row" key={`${citation.chunk_id ?? index}-${citation.section_title ?? "source"}`}>
              <strong>{citation.section_title ?? "课程引用"}</strong>
              <span>{citation.source_title ?? "课程资料"}</span>
              {citation.page_number ? <small>第 {citation.page_number} 页</small> : null}
            </article>
          )) : <p className="studio-drawer-empty">当前资源没有可展示引用。</p>}
        </section>
      ) : null}

      {props.detailTab === "trace" ? (
        <section role="tabpanel" aria-label="资源生成链路">
          {props.traceError ? (
            <InlineFeedback message="资源生成轨迹读取失败，请稍后重试。" tone="warning" />
          ) : props.traceLoading ? (
            <p className="studio-drawer-empty">正在读取资源生成链路。</p>
          ) : props.traceEvents.length > 0 ? (
            <AgentTimeline events={props.traceEvents} />
          ) : (
            <p className="studio-drawer-empty">{props.traceId ? "当前资源 trace 暂无可展示步骤。" : "当前资源没有 Agent 轨迹。"}</p>
          )}
        </section>
      ) : null}
    </div>
  );
}
