import { ArrowsClockwise, MagicWand, SlidersHorizontal, X } from "@phosphor-icons/react";
import { useState, type KeyboardEvent } from "react";

import { type GeneratedResource, type ResourceGenerationAction } from "../../api/resources";
import { versionLabel } from "./studioResourceVersions";

type StudioRegenerateDialogProps = {
  resource: GeneratedResource;
  isSubmitting: boolean;
  onClose: () => void;
  onChoose: (action: Exclude<ResourceGenerationAction, "new">) => void;
};

export function StudioRegenerateDialog(props: StudioRegenerateDialogProps) {
  return (
    <div className="studio-modal-layer" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !props.isSubmitting) props.onClose();
    }}>
      <section
        className="studio-regenerate-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="重新生成资源"
        onKeyDown={(event) => closeOnEscape(event, props.onClose, props.isSubmitting)}
      >
        <header>
          <div><h2>重新生成资源</h2><p>{props.resource.title}</p></div>
          <button type="button" aria-label="关闭重新生成" disabled={props.isSubmitting} onClick={props.onClose}>
            <X size={19} weight="bold" />
          </button>
        </header>
        <p>选择这次要改变什么。旧版本会保留，可以随时切换回来。</p>
        <div className="studio-regenerate-options">
          <button type="button" disabled={props.isSubmitting} onClick={() => props.onChoose("alternative")}>
            <MagicWand size={23} weight="duotone" />
            <span><strong>换一种教法</strong><small>保持学习目标和资料依据，改变策略、案例或学习活动。</small></span>
          </button>
          <button type="button" disabled={props.isSubmitting} onClick={() => props.onChoose("refine")}>
            <SlidersHorizontal size={23} weight="duotone" />
            <span><strong>优化当前版本</strong><small>保留教学意图，修正内容、结构、表达和交互质量。</small></span>
          </button>
        </div>
      </section>
    </div>
  );
}

type StudioVersionCompareDialogProps = {
  current: GeneratedResource;
  versions: GeneratedResource[];
  onClose: () => void;
};

export function StudioVersionCompareDialog(props: StudioVersionCompareDialogProps) {
  const currentIndex = Math.max(0, props.versions.findIndex((item) => item.id === props.current.id));
  const [leftId, setLeftId] = useState(props.current.id);
  const [rightId, setRightId] = useState(props.versions[currentIndex + 1]?.id ?? props.versions[0]?.id ?? props.current.id);
  const left = props.versions.find((item) => item.id === leftId) ?? props.current;
  const right = props.versions.find((item) => item.id === rightId) ?? props.current;

  return (
    <div className="studio-modal-layer studio-compare-layer" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) props.onClose();
    }}>
      <section
        className="studio-compare-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="比较资源版本"
        onKeyDown={(event) => closeOnEscape(event, props.onClose, false)}
      >
        <header>
          <div><h2>比较版本</h2><p>{props.current.title}</p></div>
          <button type="button" aria-label="关闭版本比较" onClick={props.onClose}><X size={19} weight="bold" /></button>
        </header>
        <div className="studio-compare-selectors">
          <VersionSelect label="左侧版本" versions={props.versions} value={leftId} onChange={setLeftId} />
          <ArrowsClockwise size={20} aria-hidden="true" />
          <VersionSelect label="右侧版本" versions={props.versions} value={rightId} onChange={setRightId} />
        </div>
        <div className="studio-compare-grid">
          <VersionSummary resource={left} />
          <VersionSummary resource={right} />
        </div>
      </section>
    </div>
  );
}

function VersionSelect(props: {
  label: string;
  versions: GeneratedResource[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{props.label}</span>
      <select value={props.value} onChange={(event) => props.onChange(event.target.value)}>
        {props.versions.map((resource) => (
          <option key={resource.id} value={resource.id}>
            {versionLabel(resource)} · {generationActionLabel(resource.generation_action)}
          </option>
        ))}
      </select>
    </label>
  );
}

function VersionSummary({ resource }: { resource: GeneratedResource }) {
  const intent = resource.intent_summary ?? resource.content_json.intent;
  const personalization = resource.personalization_summary ?? resource.content_json.personalization_summary;
  const markdown = String(resource.content_json.markdown ?? "").trim();
  return (
    <article className="studio-version-summary">
      <div className="studio-version-summary-title">
        <strong>{versionLabel(resource)}</strong>
        <span>{generationActionLabel(resource.generation_action)}</span>
      </div>
      <dl>
        <div><dt>教学策略</dt><dd>{friendlyIntentValue(intent?.teaching_strategy)}</dd></div>
        <div><dt>认知层级</dt><dd>{friendlyIntentValue(intent?.cognitive_level)}</dd></div>
        <div><dt>案例方向</dt><dd>{intent?.example_direction || "未记录"}</dd></div>
        <div><dt>学习问题</dt><dd>{personalization?.learning_problem || "未记录"}</dd></div>
      </dl>
      <section aria-label={`${versionLabel(resource)}内容摘要`}>
        <h3>内容摘要</h3>
        <p>{markdown ? markdown.slice(0, 900) : "该版本没有可比较的文本摘要。"}</p>
      </section>
    </article>
  );
}

function generationActionLabel(action: ResourceGenerationAction | undefined) {
  if (action === "alternative") return "换一种教法";
  if (action === "refine") return "优化版本";
  return "初始生成";
}

function friendlyIntentValue(value: string | undefined) {
  if (!value) return "未记录";
  const labels: Record<string, string> = {
    evidence_to_concept: "从证据建立概念",
    relationship_mapping: "梳理概念关系",
    misconception_transfer: "误区辨析与迁移",
    executable_experiment: "可运行实验",
    guided_lesson: "引导式课程",
    process_visualization: "过程可视化",
    scaffolded_foundation: "分步巩固基础",
    derivation_first: "先推导后应用",
    worked_example_first: "先看完整例题",
    framework_first: "先建立整体框架",
    code_first_experiment: "先动手验证",
    understand: "理解",
    apply: "应用",
    analyze: "分析",
    create: "创造"
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function closeOnEscape(event: KeyboardEvent<HTMLElement>, onClose: () => void, disabled: boolean) {
  if (event.key === "Escape" && !disabled) onClose();
}
