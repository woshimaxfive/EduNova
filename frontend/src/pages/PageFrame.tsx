import { type ReactNode, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { PATHS, buildCoursePath } from "../app/routePaths";
import { getDashboardSummary } from "../api/dashboard";
import { AppSidebar } from "../components/layout/AppSidebar";
import { useHomeConversationHistory } from "../features/home/useHomeConversationHistory";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useResponsiveSidebarState } from "../components/layout/useResponsiveSidebarState";
import { createTutorSession, deleteTutorSession, listTutorSessions, renameTutorSession } from "../api/tutor";

type PageFrameProps = {
  title: string;
  children: ReactNode;
  variant?: "standard" | "wide-workspace";
  titleMode?: "visible" | "sr-only";
  courseId?: number | null;
};

export function PageFrame({ title, children, variant = "standard", titleMode = "visible", courseId = null }: PageFrameProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [historySearch, setHistorySearch] = useState("");
  const hasCourseContext = Number.isFinite(courseId) && Number(courseId) > 0;
  const dashboardQuery = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getDashboardSummary, staleTime: 30_000 });
  const historyQuery = useHomeConversationHistory("", !hasCourseContext);
  const historySearchQuery = useHomeConversationHistory(historySearch, !hasCourseContext && Boolean(historySearch));
  const courseSessionsQuery = useQuery({
    queryKey: ["tutor", "sessions", "course", courseId],
    queryFn: () => listTutorSessions("course", Number(courseId)),
    enabled: hasCourseContext,
    staleTime: 10_000
  });
  const pagedHomeThreads = (historyQuery.data?.pages ?? []).flatMap((page) =>
    (page.data?.items ?? []).map(({ id, title: threadTitle, updated_at }) => ({ id, title: threadTitle, meta: updated_at.slice(0, 10) }))
  );
  const homeThreads = pagedHomeThreads.length > 0
    ? pagedHomeThreads
    : (dashboardQuery.data?.data.recent_conversations ?? []).map(({ id, title: threadTitle, meta }) => ({ id, title: threadTitle, meta }));
  const searchThreads = (historySearchQuery.data?.pages ?? []).flatMap((page) =>
    (page.data?.items ?? []).map(({ id, title: threadTitle, match_snippet }) => ({ id, title: threadTitle, meta: match_snippet || "历史会话" }))
  );
  const courseThreads = (courseSessionsQuery.data?.data ?? []).map(({ id, title: threadTitle, updated_at }) => ({ id, title: threadTitle, meta: updated_at.slice(0, 10) }));
  const conversations = hasCourseContext ? courseThreads : homeThreads;

  function goHome() {
    navigate(hasCourseContext ? buildCoursePath(Number(courseId)) : PATHS.app, { state: null });
  }

  async function createCourseConversation() {
    if (!hasCourseContext) return;
    const created = await createTutorSession({
      scope: "course",
      course_id: Number(courseId),
      mode: "chat",
      title: "新建课程对话"
    });
    await queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
    navigate(`${buildCoursePath(Number(courseId))}?course_session_id=${created.data.id}`);
  }

  async function renameCourseConversation(conversation: { id: string }, nextTitle: string) {
    if (!hasCourseContext || !nextTitle.trim()) return;
    await renameTutorSession(conversation.id, { title: nextTitle.trim() });
    await queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
  }

  async function deleteCourseConversation(conversation: { id: string }) {
    if (!hasCourseContext) return;
    await deleteTutorSession(conversation.id);
    await queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
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
          conversations={conversations}
          activeConversationId={hasCourseContext ? searchParams.get("course_session_id") : undefined}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onHomeClick={goHome}
          onNewChat={hasCourseContext ? () => void createCourseConversation() : goHome}
          onSelectConversation={hasCourseContext ? (conversation) =>
            navigate(`${buildCoursePath(Number(courseId))}?course_session_id=${conversation.id}`)
            : (conversation) =>
              navigate(`${PATHS.app}?session_id=${conversation.id}`, {
                state: {
                  selectedHomeThreadId: conversation.id
                }
              })
          }
          onRenameConversation={hasCourseContext ? renameCourseConversation : undefined}
          onDeleteConversation={hasCourseContext ? deleteCourseConversation : undefined}
          hasMoreConversations={!hasCourseContext && Boolean(historyQuery.hasNextPage)}
          isLoadingMoreConversations={!hasCourseContext && historyQuery.isFetchingNextPage}
          onLoadMoreConversations={!hasCourseContext ? () => void historyQuery.fetchNextPage() : undefined}
          historySearchResults={!hasCourseContext && historySearch ? searchThreads : undefined}
          historySearchPending={!hasCourseContext && historySearchQuery.isPending && Boolean(historySearch)}
          historySearchError={!hasCourseContext && historySearchQuery.isError}
          historySearchHasMore={!hasCourseContext && Boolean(historySearchQuery.hasNextPage)}
          historySearchLoadingMore={!hasCourseContext && historySearchQuery.isFetchingNextPage}
          onHistorySearch={!hasCourseContext ? setHistorySearch : undefined}
          onRetryHistorySearch={!hasCourseContext ? () => void historySearchQuery.refetch() : undefined}
          onLoadMoreHistorySearch={!hasCourseContext ? () => void historySearchQuery.fetchNextPage() : undefined}
        />
        <section className={variant === "wide-workspace" ? "route-main-surface route-main-surface-wide" : "route-main-surface"}>
          <header className={titleMode === "sr-only" ? "route-titlebar route-titlebar-sr-only" : "route-titlebar"}>
            <h1 className={titleMode === "sr-only" ? "visually-hidden" : undefined}>{title}</h1>
          </header>
          <section className="page-workbench">{children}</section>
        </section>
      </section>
    </LearningSpaceShell>
  );
}
