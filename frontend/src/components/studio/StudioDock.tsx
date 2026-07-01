import { Notebook, Sparkle } from "@phosphor-icons/react";

import { type StudioOutput } from "../../types/api";

type StudioDockProps = {
  outputs: StudioOutput[];
};

export function StudioDock({ outputs }: StudioDockProps) {
  return (
    <section className="studio-dock" role="region" aria-label="Studio 生成区">
      <div className="section-heading-line">
        <div>
          <p className="section-kicker">Studio</p>
          <h2>资源生成工作台</h2>
        </div>
        <button className="soft-button" type="button">
          <Sparkle size={17} weight="fill" aria-hidden="true" />
          <span>生成资源</span>
        </button>
      </div>
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
