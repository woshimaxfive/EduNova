import { type ReactNode } from "react";

import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

type PageFrameProps = {
  kicker: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function PageFrame({ kicker, title, description, children }: PageFrameProps) {
  return (
    <LearningSpaceShell>
      <section className="workspace-hero slim">
        <div>
          <p className="section-kicker">{kicker}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </section>
      <section className="page-workbench">{children}</section>
    </LearningSpaceShell>
  );
}
