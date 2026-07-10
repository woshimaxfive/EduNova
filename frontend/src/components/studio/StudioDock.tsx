import { Notebook, Sparkle } from "@phosphor-icons/react";

import { type GeneratedResource } from "../../api/resources";

type StudioDockProps = {
  outputs: GeneratedResource[];
  selectedResourceId?: string | null;
  onGenerate?: () => void;
  onSelectResource?: (resourceId: string) => void;
  showGenerateAction?: boolean;
};

const resourceTypeLabels: Record<GeneratedResource["resource_type"], string> = {
  doc: "讲解",
  mindmap: "思维导图",
  quiz: "练习",
  code: "代码实操",
  slide: "PPT",
  animation: "动画图解"
};

function generationModeLabel(output: GeneratedResource) {
  const generationMode = output.content_json.metadata?.generation_mode;
  if (output.review_status === "low_evidence" || generationMode === "low_evidence_fallback") {
    return "低依据";
  }
  if (generationMode === "model_enhanced") {
    return "模型增强";
  }
  if (generationMode === "deterministic_source") {
    return "本地可用稿";
  }
  if (output.review_status === "failed") {
    return "生成失败";
  }
  if (output.review_status === "passed") {
    return "可使用";
  }
  return "待生成";
}

function isLowEvidence(output: GeneratedResource) {
  return output.review_status === "low_evidence" || output.content_json.metadata?.generation_mode === "low_evidence_fallback";
}

export function StudioDock({ outputs, selectedResourceId, onGenerate, onSelectResource, showGenerateAction = true }: StudioDockProps) {
  const handleGenerate = onGenerate ?? (() => undefined);
  const activeResourceId = selectedResourceId ?? outputs[0]?.id ?? null;

  return (
    <section className="studio-dock" role="region" aria-label="资源生成区">
      <div className="section-heading-line">
        <div>
          <h2>资源输出</h2>
        </div>
        {showGenerateAction ? (
          <button className="soft-button" type="button" onClick={handleGenerate}>
            <Sparkle size={17} weight="fill" aria-hidden="true" />
            <span>生成资源</span>
          </button>
        ) : null}
      </div>
      <div className="studio-track">
        {outputs.length > 0 ? (
          outputs.map((output) => {
            const statusLabel = generationModeLabel(output);
            const isSelected = output.id === activeResourceId;

            return (
              <button
                className={`studio-item ${isLowEvidence(output) ? "low-evidence" : ""} ${isSelected ? "active" : ""}`}
                key={output.id}
                type="button"
                aria-label={`查看资源 ${output.title}`}
                aria-pressed={isSelected}
                onClick={() => onSelectResource?.(output.id)}
              >
                <Notebook size={18} weight="duotone" aria-hidden="true" />
                <div>
                  <small>{resourceTypeLabels[output.resource_type]}</small>
                  <strong>{output.title}</strong>
                </div>
                <span>{statusLabel}</span>
              </button>
            );
          })
        ) : (
          <p className="empty-inline-note">还没有生成资源</p>
        )}
      </div>
    </section>
  );
}
