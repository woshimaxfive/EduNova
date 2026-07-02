import { type ReactNode, useState } from "react";

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

export function PageFrame({ title, description, children }: PageFrameProps) {
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
          onNewChat={() => showNotice("已准备新建一条主页独立对话，回到学习主页后可以继续输入。", "success")}
          onSearchHistory={() => showNotice("历史搜索会在对话索引接口接入后开放。")}
          onSelectConversation={(conversation) => showNotice(`已定位到主页历史「${conversation.title}」。课程内历史会在课程空间单独显示。`, "success")}
        />
        <section className="route-main-surface">
          <section className="workspace-hero slim">
            <div>
              <h1>{title}</h1>
              <p>{description}</p>
            </div>
          </section>
          <section className="page-workbench">{children}</section>
          <ActionNotice notice={notice} className="route-action-notice" />
        </section>
      </section>
    </LearningSpaceShell>
  );
}
