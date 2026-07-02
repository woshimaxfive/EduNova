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
import { Link, NavLink, useNavigate } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { useAuthStore } from "../../features/auth/authStore";

export type SidebarConversation = {
  id: string;
  title: string;
  meta: string;
};

type AppSidebarProps = {
  isCollapsed: boolean;
  conversations?: SidebarConversation[];
  onToggleCollapsed: () => void;
  onNewChat?: () => void;
  onSearchHistory?: () => void;
  onSelectConversation?: (conversation: SidebarConversation) => void;
};

export function AppSidebar({
  isCollapsed,
  conversations = [],
  onToggleCollapsed,
  onNewChat,
  onSearchHistory,
  onSelectConversation
}: AppSidebarProps) {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);

  function logout() {
    clearSession();
    navigate(PATHS.login);
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

      <button className="new-chat-button" type="button" onClick={onNewChat}>
        <Plus size={17} weight="bold" aria-hidden="true" />
        <span>新建对话</span>
      </button>
      <button className="history-search-button" type="button" onClick={onSearchHistory}>
        <MagnifyingGlass size={16} weight="duotone" aria-hidden="true" />
        <span>搜索历史</span>
      </button>
      <div className="home-rail-heading">
        <span>最近</span>
        <ClockCounterClockwise size={18} weight="duotone" aria-hidden="true" />
      </div>
      <div className="home-thread-list">
        {conversations.length > 0 ? (
          conversations.map((conversation) => (
            <button className="home-thread" key={conversation.id} type="button" onClick={() => onSelectConversation?.(conversation)}>
              <strong>{conversation.title}</strong>
              <small>{conversation.meta}</small>
            </button>
          ))
        ) : (
          <p className="home-thread-empty">还没有历史对话</p>
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
