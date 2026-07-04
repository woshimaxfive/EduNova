import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

type PageFrameProps = {
  title: string;
  children: ReactNode;
};

export function PageFrame({ title, children }: PageFrameProps) {
  const navigate = useNavigate();
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);

  return (
    <LearningSpaceShell hideTopNavigation>
      <section className={isHistoryCollapsed ? "app-workspace-layout history-collapsed" : "app-workspace-layout"}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={[]}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onNewChat={() => navigate(PATHS.app)}
        />
        <section className="route-main-surface">
          <header className="route-titlebar">
            <h1>{title}</h1>
          </header>
          <section className="page-workbench">{children}</section>
        </section>
      </section>
    </LearningSpaceShell>
  );
}
