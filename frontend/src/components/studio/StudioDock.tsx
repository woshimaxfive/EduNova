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
  slide: "PPT 大纲"
};

function reviewStatusLabel(status: string) {
  if (status === "passed") {
    return "可使用";
  }
  if (status === "low_evidence") {
    return "低依据";
  }
  if (status === "failed") {
    return "生成失败";
  }
  return "待生成";
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
            const statusLabel = reviewStatusLabel(output.review_status);
            const isSelected = output.id === activeResourceId;

            return (
              <button
                className={`studio-item ${output.review_status === "low_evidence" ? "low-evidence" : ""} ${isSelected ? "active" : ""}`}
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
