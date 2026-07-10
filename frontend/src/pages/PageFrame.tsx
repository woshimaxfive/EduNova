import { type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { getDashboardSummary } from "../api/dashboard";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useResponsiveSidebarState } from "../components/layout/useResponsiveSidebarState";

type PageFrameProps = {
  title: string;
  children: ReactNode;
};

export function PageFrame({ title, children }: PageFrameProps) {
  const navigate = useNavigate();
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    staleTime: 30_000
  });
  const recentConversations = dashboardQuery.data?.data.recent_conversations ?? [];
  const homeThreads = recentConversations.map(({ id, title: threadTitle, meta }) => ({
    id,
    title: threadTitle,
    meta
  }));

  function goHome() {
    navigate(PATHS.app, { state: null });
  }

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
          conversations={homeThreads}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onHomeClick={goHome}
          onNewChat={goHome}
          onSelectConversation={(conversation) =>
            navigate(PATHS.app, {
              state: {
                selectedHomeThreadId: conversation.id
              }
            })
          }
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
