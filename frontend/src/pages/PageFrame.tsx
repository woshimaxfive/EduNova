import { type ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { getDashboardSummary } from "../api/dashboard";
import { AppSidebar } from "../components/layout/AppSidebar";
import { useHomeConversationHistory } from "../features/home/useHomeConversationHistory";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useResponsiveSidebarState } from "../components/layout/useResponsiveSidebarState";

type PageFrameProps = {
  title: string;
  children: ReactNode;
  variant?: "standard" | "wide-workspace";
};

export function PageFrame({ title, children, variant = "standard" }: PageFrameProps) {
  const navigate = useNavigate();
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [historySearch, setHistorySearch] = useState("");
  const dashboardQuery = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getDashboardSummary, staleTime: 30_000 });
  const historyQuery = useHomeConversationHistory();
  const historySearchQuery = useHomeConversationHistory(historySearch, Boolean(historySearch));
  const pagedHomeThreads = (historyQuery.data?.pages ?? []).flatMap((page) =>
    (page.data?.items ?? []).map(({ id, title: threadTitle, updated_at }) => ({ id, title: threadTitle, meta: updated_at.slice(0, 10) }))
  );
  const homeThreads = pagedHomeThreads.length > 0
    ? pagedHomeThreads
    : (dashboardQuery.data?.data.recent_conversations ?? []).map(({ id, title: threadTitle, meta }) => ({ id, title: threadTitle, meta }));
  const searchThreads = (historySearchQuery.data?.pages ?? []).flatMap((page) =>
    (page.data?.items ?? []).map(({ id, title: threadTitle, match_snippet }) => ({ id, title: threadTitle, meta: match_snippet || "历史会话" }))
  );

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
          hasMoreConversations={Boolean(historyQuery.hasNextPage)}
          isLoadingMoreConversations={historyQuery.isFetchingNextPage}
          onLoadMoreConversations={() => void historyQuery.fetchNextPage()}
          historySearchResults={historySearch ? searchThreads : undefined}
          historySearchPending={historySearchQuery.isPending && Boolean(historySearch)}
          historySearchError={historySearchQuery.isError}
          historySearchHasMore={Boolean(historySearchQuery.hasNextPage)}
          historySearchLoadingMore={historySearchQuery.isFetchingNextPage}
          onHistorySearch={setHistorySearch}
          onRetryHistorySearch={() => void historySearchQuery.refetch()}
          onLoadMoreHistorySearch={() => void historySearchQuery.fetchNextPage()}
          onSelectConversation={(conversation) =>
            navigate(`${PATHS.app}?session_id=${conversation.id}`, {
              state: {
                selectedHomeThreadId: conversation.id
              }
            })
          }
        />
        <section className={variant === "wide-workspace" ? "route-main-surface route-main-surface-wide" : "route-main-surface"}>
          <header className="route-titlebar">
            <h1>{title}</h1>
          </header>
          <section className="page-workbench">{children}</section>
        </section>
      </section>
    </LearningSpaceShell>
  );
}
