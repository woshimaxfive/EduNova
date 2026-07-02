import { type ReactNode, useState } from "react";

import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

type PageFrameProps = {
  kicker: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function PageFrame({ kicker, title, description, children }: PageFrameProps) {
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);

  return (
    <LearningSpaceShell hideTopNavigation>
      <section className={isHistoryCollapsed ? "app-workspace-layout history-collapsed" : "app-workspace-layout"}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar isCollapsed={isHistoryCollapsed} onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)} />
        <section className="route-main-surface">
          <section className="workspace-hero slim">
            <div>
              <p className="section-kicker">{kicker}</p>
              <h1>{title}</h1>
              <p>{description}</p>
            </div>
          </section>
          <section className="page-workbench">{children}</section>
        </section>
      </section>
    </LearningSpaceShell>
  );
}
