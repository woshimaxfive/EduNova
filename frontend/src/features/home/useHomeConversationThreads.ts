import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { deleteTutorSession, renameTutorSession, type TutorSessionSummary } from "../../api/tutor";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import type {
  DashboardSummaryResponse,
  DashboardSummaryThread
} from "./homeLearningModel";
import { useHomeConversationHistory } from "./useHomeConversationHistory";

type HomeConversationThreadsParams = {
  activeThreadId: string | null;
  enabled: boolean;
  fallbackThreads: DashboardSummaryResponse["data"]["recent_conversations"];
  onDeleteActive: () => void;
  onFeedback: (feedback: { message: string; tone: FeedbackTone } | null) => void;
};

export function useHomeConversationThreads({
  activeThreadId,
  enabled,
  fallbackThreads,
  onDeleteActive,
  onFeedback
}: HomeConversationThreadsParams) {
  const queryClient = useQueryClient();
  const [localThreads, setLocalThreads] = useState<DashboardSummaryThread[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const historyQuery = useHomeConversationHistory("", enabled);
  const historySearchQuery = useHomeConversationHistory(historySearch, enabled && Boolean(historySearch));

  const serverThreads = useMemo(
    () => (historyQuery.data?.pages ?? []).flatMap((page) =>
      (page.data?.items ?? []).map(({ id, title, updated_at }) => ({
        id,
        title,
        meta: updated_at.slice(0, 10)
      }))
    ),
    [historyQuery.data?.pages]
  );
  const homeThreads = useMemo(() => {
    const localIds = new Set(localThreads.map((thread) => thread.id));
    const persistedThreads = serverThreads.length > 0 ? serverThreads : fallbackThreads;

    return [...localThreads, ...persistedThreads.filter((thread) => !localIds.has(thread.id))];
  }, [fallbackThreads, localThreads, serverThreads]);
  const historySearchThreads = useMemo(
    () => (historySearchQuery.data?.pages ?? []).flatMap((page) =>
      (page.data?.items ?? []).map(({ id, title, match_snippet }) => ({
        id,
        title,
        meta: match_snippet || "历史会话"
      }))
    ),
    [historySearchQuery.data?.pages]
  );

  function updateDashboardThreads(
    updater: (threads: DashboardSummaryResponse["data"]["recent_conversations"])
      => DashboardSummaryResponse["data"]["recent_conversations"]
  ) {
    queryClient.setQueryData<DashboardSummaryResponse>(["dashboard", "summary"], (current) =>
      current
        ? {
            ...current,
            data: {
              ...current.data,
              recent_conversations: updater(current.data.recent_conversations)
            }
          }
        : current
    );
  }

  function upsertThread(session: TutorSessionSummary) {
    const nextThread: DashboardSummaryThread = {
      id: session.id,
      title: session.title,
      meta: "刚刚"
    };
    setLocalThreads((current) => [nextThread, ...current.filter((thread) => thread.id !== nextThread.id)]);
    void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
  }

  async function renameConversation(conversation: DashboardSummaryThread, title: string) {
    const normalizedTitle = title.trim();
    if (!normalizedTitle) return;

    try {
      const renamed = await renameTutorSession(conversation.id, { title: normalizedTitle });
      const renamedTitle = renamed.data.title;
      setLocalThreads((current) =>
        current.map((thread) => thread.id === conversation.id ? { ...thread, title: renamedTitle } : thread)
      );
      updateDashboardThreads((threads) =>
        threads.map((thread) => thread.id === conversation.id ? { ...thread, title: renamedTitle } : thread)
      );
      onFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
    } catch {
      onFeedback({ message: "会话改名失败，请稍后再试。", tone: "warning" });
    }
  }

  async function deleteConversation(conversation: DashboardSummaryThread) {
    try {
      await deleteTutorSession(conversation.id);
      setLocalThreads((current) => current.filter((thread) => thread.id !== conversation.id));
      updateDashboardThreads((threads) => threads.filter((thread) => thread.id !== conversation.id));
      if (activeThreadId === conversation.id) onDeleteActive();
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
    } catch {
      onFeedback({ message: "会话删除失败，请稍后再试。", tone: "warning" });
    }
  }

  return {
    deleteConversation,
    historyQuery,
    historySearch,
    historySearchQuery,
    historySearchThreads,
    homeThreads,
    renameConversation,
    setHistorySearch,
    upsertThread
  };
}
