import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { homeConversations } from "../data/demoConversations";
import { useAuthStore } from "../features/auth/authStore";

type PageFrameProps = {
  title: string;
  description: string;
  children: ReactNode;
};

export function PageFrame({ title, children }: PageFrameProps) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const { notice, showNotice } = useActionNotice();
  const conversations = user?.starterMode === "blank" ? [] : homeConversations;

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
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onNewChat={() => navigate(PATHS.app)}
          onSelectConversation={(conversation) => showNotice(`已定位到「${conversation.title}」。`, "success")}
        />
        <section className="route-main-surface">
          <header className="route-titlebar">
            <h1>{title}</h1>
          </header>
          <section className="page-workbench">{children}</section>
          <ActionNotice notice={notice} className="route-action-notice" />
        </section>
      </section>
    </LearningSpaceShell>
  );
}
