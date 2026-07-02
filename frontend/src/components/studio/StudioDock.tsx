import { Notebook, Sparkle } from "@phosphor-icons/react";

import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";
import { type StudioOutput } from "../../types/api";

type StudioDockProps = {
  outputs: StudioOutput[];
  onGenerate?: () => void;
  showGenerateAction?: boolean;
};

export function StudioDock({ outputs, onGenerate, showGenerateAction = true }: StudioDockProps) {
  const { notice, showNotice } = useActionNotice();
  const handleGenerate = onGenerate ?? (() => showNotice("已加入生成队列。"));

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
      <ActionNotice notice={notice} />
      <div className="studio-track">
        {outputs.map((output) => (
          <article className={`studio-item ${output.reviewStatus === "低依据" ? "low-evidence" : ""}`} key={output.id}>
            <Notebook size={18} weight="duotone" aria-hidden="true" />
            <div>
              <small>{output.resourceType}</small>
              <strong>{output.title}</strong>
            </div>
            <span>{output.reviewStatus}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
