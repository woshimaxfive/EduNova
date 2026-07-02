import {
  BookOpen,
  CaretLeft,
  CaretRight,
  ClockCounterClockwise,
  GearSix,
  MagnifyingGlass,
  Plus,
  SignOut,
  Sparkle,
  Student,
  UserCircle
} from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";
import { useAuthStore } from "../../features/auth/authStore";

export type SidebarConversation = {
  id: string;
  title: string;
  meta: string;
};

type AppSidebarProps = {
  isCollapsed: boolean;
  conversations?: SidebarConversation[];
  activeConversationId?: string | null;
  onToggleCollapsed: () => void;
  onNewChat?: () => void;
  onSearchHistory?: () => void;
  onSelectConversation?: (conversation: SidebarConversation) => void;
};

export function AppSidebar({
  isCollapsed,
  conversations = [],
  activeConversationId,
  onToggleCollapsed,
  onNewChat,
  onSearchHistory,
  onSelectConversation
}: AppSidebarProps) {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);
  const { notice, showNotice } = useActionNotice();
  const [isHistorySearchOpen, setIsHistorySearchOpen] = useState(false);
  const [historySearchTerm, setHistorySearchTerm] = useState("");
  const historySearchInputRef = useRef<HTMLInputElement | null>(null);
  const trimmedHistorySearchTerm = historySearchTerm.trim().toLowerCase();
  const visibleConversations = useMemo(
    () =>
      trimmedHistorySearchTerm
        ? conversations.filter((conversation) =>
            `${conversation.title} ${conversation.meta}`.toLowerCase().includes(trimmedHistorySearchTerm)
          )
        : conversations,
    [conversations, trimmedHistorySearchTerm]
  );

  useEffect(() => {
    if (isHistorySearchOpen && !isCollapsed) {
      historySearchInputRef.current?.focus();
    }
  }, [isHistorySearchOpen, isCollapsed]);

  function logout() {
    clearSession();
    navigate(PATHS.login);
  }

  function handleNewChat() {
    setHistorySearchTerm("");
    setIsHistorySearchOpen(false);

    if (onNewChat) {
      onNewChat();
      return;
    }

    navigate(PATHS.app);
  }

  function handleSearchHistory() {
    setIsHistorySearchOpen(true);

    if (onSearchHistory) {
      onSearchHistory();
      return;
    }

    showNotice("输入关键词筛选历史。");
  }

  const sidebarLinkClassName = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : undefined);
  const accountLinkClassName = ({ isActive }: { isActive: boolean }) => (isActive ? "home-account-link active" : "home-account-link");

  return (
    <section className="home-history-rail" aria-label="历史对话" data-collapsed={isCollapsed ? "true" : "false"}>
      <div className="home-sidebar-brand">
        <Link className="brand-mark home-brand" to={PATHS.app} aria-label="EduNova 首页">
          <span className="brand-symbol" aria-hidden="true">
            <Student size={22} weight="duotone" />
          </span>
          <span className="home-sidebar-label">EduNova</span>
        </Link>
        <button
          className="sidebar-collapse-button"
          type="button"
          aria-label={isCollapsed ? "展开侧栏" : "收起侧栏"}
          aria-expanded={!isCollapsed}
          onClick={onToggleCollapsed}
        >
          {isCollapsed ? <CaretRight size={17} weight="bold" aria-hidden="true" /> : <CaretLeft size={17} weight="bold" aria-hidden="true" />}
        </button>
      </div>

      <nav className="home-sidebar-nav" aria-label="主页导航">
        <NavLink to={PATHS.library} className={sidebarLinkClassName}>
          <BookOpen size={18} weight="duotone" aria-hidden="true" />
          <span>资料库</span>
        </NavLink>
        <NavLink to={PATHS.studio} className={sidebarLinkClassName}>
          <Sparkle size={18} weight="duotone" aria-hidden="true" />
          <span>资源工坊</span>
        </NavLink>
      </nav>

      <button className="new-chat-button" type="button" onClick={handleNewChat}>
        <Plus size={17} weight="bold" aria-hidden="true" />
        <span>新建对话</span>
      </button>
      <button
        className={isHistorySearchOpen ? "history-search-button active" : "history-search-button"}
        type="button"
        aria-expanded={isHistorySearchOpen}
        onClick={handleSearchHistory}
      >
        <MagnifyingGlass size={16} weight="duotone" aria-hidden="true" />
        <span>搜索历史</span>
      </button>
      {isHistorySearchOpen && !isCollapsed ? (
        <label className="history-search-field">
          <MagnifyingGlass size={15} weight="duotone" aria-hidden="true" />
          <span className="visually-hidden">搜索历史关键词</span>
          <input
            ref={historySearchInputRef}
            type="search"
            aria-label="搜索历史关键词"
            value={historySearchTerm}
            placeholder="输入关键词"
            onChange={(event) => setHistorySearchTerm(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setHistorySearchTerm("");
                setIsHistorySearchOpen(false);
              }
            }}
          />
        </label>
      ) : null}
      <ActionNotice notice={notice} className="sidebar-action-notice" />
      <div className="home-rail-heading">
        <span>最近</span>
        <ClockCounterClockwise size={18} weight="duotone" aria-hidden="true" />
      </div>
      <div className="home-thread-list">
        {visibleConversations.length > 0 ? (
          visibleConversations.map((conversation) => (
            <button
              className={activeConversationId === conversation.id ? "home-thread active" : "home-thread"}
              key={conversation.id}
              type="button"
              aria-pressed={activeConversationId === conversation.id}
              onClick={() => onSelectConversation?.(conversation)}
            >
              <strong>{conversation.title}</strong>
              <small>{conversation.meta}</small>
            </button>
          ))
        ) : (
          <p className="home-thread-empty">{conversations.length > 0 ? "没有匹配的历史" : "还没有历史对话"}</p>
        )}
      </div>
      <div className="home-account-section" aria-label="账号入口">
        <NavLink className={accountLinkClassName} to={PATHS.profile}>
          <UserCircle size={18} weight="duotone" aria-hidden="true" />
          <span>个人资料</span>
        </NavLink>
        <NavLink className={accountLinkClassName} to={PATHS.settings}>
          <GearSix size={18} weight="duotone" aria-hidden="true" />
          <span>设置</span>
        </NavLink>
        <button className="home-account-link" type="button" onClick={logout}>
          <SignOut size={18} weight="duotone" aria-hidden="true" />
          <span>退出登录</span>
        </button>
        <div className="home-user-mini">
          <span>{user?.displayName?.slice(0, 1) ?? "学"}</span>
          <strong>{user?.displayName ?? "学生"}</strong>
        </div>
      </div>
    </section>
  );
}
