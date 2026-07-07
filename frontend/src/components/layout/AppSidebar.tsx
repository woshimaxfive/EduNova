import {
  BookOpen,
  CaretLeft,
  CaretRight,
  ChatCircle,
  Check,
  ClockCounterClockwise,
  DotsThree,
  GearSix,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  SignOut,
  Sparkle,
  Student,
  Trash,
  UserCircle,
  X
} from "@phosphor-icons/react";
import { type FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
  activeConversationId?: string | null;
  onToggleCollapsed: () => void;
  onHomeClick?: () => void;
  onNewChat?: () => void;
  onSelectConversation?: (conversation: SidebarConversation) => void;
  onRenameConversation?: (conversation: SidebarConversation, title: string) => void | Promise<void>;
  onDeleteConversation?: (conversation: SidebarConversation) => void | Promise<void>;
};

export function AppSidebar({
  isCollapsed,
  conversations = [],
  activeConversationId,
  onToggleCollapsed,
  onHomeClick,
  onNewChat,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation
}: AppSidebarProps) {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);
  const [isHistorySearchOpen, setIsHistorySearchOpen] = useState(false);
  const [historySearchTerm, setHistorySearchTerm] = useState("");
  const [openConversationMenuId, setOpenConversationMenuId] = useState<string | null>(null);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [confirmingDeleteConversationId, setConfirmingDeleteConversationId] = useState<string | null>(null);
  const [busyConversationId, setBusyConversationId] = useState<string | null>(null);
  const threadListRef = useRef<HTMLDivElement | null>(null);
  const pendingThreadListScrollTopRef = useRef<number | null>(null);
  const historySearchInputRef = useRef<HTMLInputElement | null>(null);
  const editingTitleInputRef = useRef<HTMLInputElement | null>(null);
  const trimmedHistorySearchTerm = historySearchTerm.trim().toLowerCase();
  const searchConversations = useMemo(
    () =>
      trimmedHistorySearchTerm
        ? conversations.filter((conversation) =>
            `${conversation.title} ${conversation.meta}`.toLowerCase().includes(trimmedHistorySearchTerm)
          )
        : conversations,
    [conversations, trimmedHistorySearchTerm]
  );

  useEffect(() => {
    if (isHistorySearchOpen) {
      historySearchInputRef.current?.focus();
    }
  }, [isHistorySearchOpen]);

  useEffect(() => {
    if (editingConversationId !== null) {
      editingTitleInputRef.current?.focus();
      editingTitleInputRef.current?.select();
    }
  }, [editingConversationId]);

  useLayoutEffect(() => {
    const scrollTop = pendingThreadListScrollTopRef.current;
    const threadList = threadListRef.current;
    if (scrollTop === null || threadList === null) {
      return;
    }

    threadList.scrollTop = scrollTop;
    pendingThreadListScrollTopRef.current = null;
  }, [activeConversationId, conversations]);

  function logout() {
    clearSession();
    navigate(PATHS.login);
  }

  function rememberThreadListScroll() {
    pendingThreadListScrollTopRef.current = threadListRef.current?.scrollTop ?? null;
  }

  function handleHomeClick() {
    setHistorySearchTerm("");
    setIsHistorySearchOpen(false);
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setConfirmingDeleteConversationId(null);
    onHomeClick?.();
  }

  function handleNewChat() {
    setHistorySearchTerm("");
    setIsHistorySearchOpen(false);
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setConfirmingDeleteConversationId(null);

    if (onNewChat) {
      onNewChat();
      return;
    }

    navigate(PATHS.app);
  }

  function handleSearchHistory() {
    setIsHistorySearchOpen(true);
  }

  function closeHistorySearch() {
    setHistorySearchTerm("");
    setIsHistorySearchOpen(false);
  }

  function selectSearchConversation(conversation: SidebarConversation) {
    onSelectConversation?.(conversation);
    closeHistorySearch();
  }

  function startRename(conversation: SidebarConversation) {
    setEditingConversationId(conversation.id);
    setEditingTitle(conversation.title);
    setOpenConversationMenuId(null);
    setConfirmingDeleteConversationId(null);
  }

  function cancelRename() {
    setEditingConversationId(null);
    setEditingTitle("");
  }

  async function submitRename(event: FormEvent<HTMLFormElement>, conversation: SidebarConversation) {
    event.preventDefault();
    const title = editingTitle.trim();
    if (!title || busyConversationId === conversation.id) {
      return;
    }

    if (title === conversation.title) {
      cancelRename();
      return;
    }

    rememberThreadListScroll();
    setBusyConversationId(conversation.id);
    try {
      await onRenameConversation?.(conversation, title);
      cancelRename();
    } finally {
      setBusyConversationId(null);
    }
  }

  async function confirmDelete(conversation: SidebarConversation) {
    if (busyConversationId === conversation.id) {
      return;
    }

    rememberThreadListScroll();
    setBusyConversationId(conversation.id);
    try {
      await onDeleteConversation?.(conversation);
      setOpenConversationMenuId(null);
      setConfirmingDeleteConversationId(null);
      if (editingConversationId === conversation.id) {
        cancelRename();
      }
    } finally {
      setBusyConversationId(null);
    }
  }

  const sidebarLinkClassName = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : undefined);
  const accountLinkClassName = ({ isActive }: { isActive: boolean }) => (isActive ? "home-account-link active" : "home-account-link");

  return (
    <>
      <section className="home-history-rail" aria-label="历史对话" data-collapsed={isCollapsed ? "true" : "false"}>
        <div className="home-sidebar-brand">
          <Link className="brand-mark home-brand" to={PATHS.app} aria-label="EduNova 首页" onClick={handleHomeClick}>
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
            {isCollapsed ? (
              <CaretRight size={17} weight="bold" aria-hidden="true" />
            ) : (
              <CaretLeft size={17} weight="bold" aria-hidden="true" />
            )}
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
          aria-haspopup="dialog"
          onClick={handleSearchHistory}
        >
          <MagnifyingGlass size={16} weight="duotone" aria-hidden="true" />
          <span>搜索历史</span>
        </button>
        <div className="home-rail-heading">
          <span>最近</span>
          <ClockCounterClockwise size={18} weight="duotone" aria-hidden="true" />
        </div>
        <div className="home-thread-list" ref={threadListRef}>
          {conversations.length > 0 ? (
            conversations.map((conversation) => (
              <div
                className={activeConversationId === conversation.id ? "home-thread active" : "home-thread"}
                key={conversation.id}
                data-editing={editingConversationId === conversation.id ? "true" : "false"}
                data-menu-open={openConversationMenuId === conversation.id ? "true" : "false"}
              >
                {editingConversationId === conversation.id ? (
                  <form className="home-thread-editor" onSubmit={(event) => void submitRename(event, conversation)}>
                    <label className="visually-hidden" htmlFor={`conversation-title-${conversation.id}`}>
                      会话名称
                    </label>
                    <input
                      id={`conversation-title-${conversation.id}`}
                      ref={editingTitleInputRef}
                      aria-label="会话名称"
                      value={editingTitle}
                      maxLength={255}
                      onChange={(event) => setEditingTitle(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          event.preventDefault();
                          cancelRename();
                        }
                      }}
                    />
                    <span className="home-thread-editor-actions">
                      <button type="submit" aria-label="保存会话名称" disabled={!editingTitle.trim() || busyConversationId === conversation.id}>
                        <Check size={14} weight="bold" aria-hidden="true" />
                      </button>
                      <button type="button" aria-label="取消重命名" onClick={cancelRename} disabled={busyConversationId === conversation.id}>
                        <X size={14} weight="bold" aria-hidden="true" />
                      </button>
                    </span>
                  </form>
                ) : (
                  <>
                    <button
                      className="home-thread-main"
                      type="button"
                      aria-current={activeConversationId === conversation.id ? "page" : undefined}
                      aria-pressed={activeConversationId === conversation.id}
                      onClick={() => {
                        rememberThreadListScroll();
                        setOpenConversationMenuId(null);
                        setConfirmingDeleteConversationId(null);
                        onSelectConversation?.(conversation);
                      }}
                    >
                      <ChatCircle className="home-thread-icon" size={16} weight="duotone" aria-hidden="true" />
                      <span className="home-thread-copy">
                        <strong>{conversation.title}</strong>
                        <small>{conversation.meta}</small>
                      </span>
                    </button>
                    {onRenameConversation || onDeleteConversation ? (
                      <button
                        className="home-thread-menu-button"
                        type="button"
                        aria-label={`打开会话操作菜单 ${conversation.id}`}
                        aria-expanded={openConversationMenuId === conversation.id}
                        aria-haspopup="menu"
                        onClick={() => {
                          setOpenConversationMenuId((current) => (current === conversation.id ? null : conversation.id));
                          setConfirmingDeleteConversationId(null);
                        }}
                      >
                        <DotsThree size={18} weight="bold" aria-hidden="true" />
                      </button>
                    ) : null}
                    {openConversationMenuId === conversation.id ? (
                      <div className="home-thread-menu" role="menu" aria-label="会话操作">
                        {confirmingDeleteConversationId === conversation.id ? (
                          <>
                            <button
                              className="home-thread-action danger"
                              type="button"
                              role="menuitem"
                              disabled={busyConversationId === conversation.id}
                              onClick={() => void confirmDelete(conversation)}
                            >
                              <Trash size={15} weight="duotone" aria-hidden="true" />
                              <span>确认删除</span>
                            </button>
                            <button
                              className="home-thread-action"
                              type="button"
                              role="menuitem"
                              disabled={busyConversationId === conversation.id}
                              onClick={() => setConfirmingDeleteConversationId(null)}
                            >
                              <X size={15} weight="bold" aria-hidden="true" />
                              <span>取消</span>
                            </button>
                          </>
                        ) : (
                          <>
                            {onRenameConversation ? (
                              <button className="home-thread-action" type="button" role="menuitem" onClick={() => startRename(conversation)}>
                                <PencilSimple size={15} weight="duotone" aria-hidden="true" />
                                <span>重命名</span>
                              </button>
                            ) : null}
                            {onDeleteConversation ? (
                              <button
                                className="home-thread-action danger"
                                type="button"
                                role="menuitem"
                                onClick={() => setConfirmingDeleteConversationId(conversation.id)}
                              >
                                <Trash size={15} weight="duotone" aria-hidden="true" />
                                <span>删除</span>
                              </button>
                            ) : null}
                          </>
                        )}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
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

      {isHistorySearchOpen ? (
        <div
          className="history-search-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeHistorySearch();
            }
          }}
        >
          <section className="history-search-dialog" role="dialog" aria-modal="true" aria-labelledby="history-search-title">
            <div className="history-search-command">
              <MagnifyingGlass size={22} weight="duotone" aria-hidden="true" />
              <label className="visually-hidden" htmlFor="history-search-input">
                搜索历史关键词
              </label>
              <input
                id="history-search-input"
                ref={historySearchInputRef}
                type="search"
                aria-label="搜索历史关键词"
                value={historySearchTerm}
                placeholder="搜索历史..."
                onChange={(event) => setHistorySearchTerm(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    closeHistorySearch();
                  }
                }}
              />
              <button type="button" aria-label="关闭搜索历史" onClick={closeHistorySearch}>
                <X size={18} weight="bold" aria-hidden="true" />
              </button>
            </div>
            <h2 id="history-search-title">搜索历史</h2>
            <div className="history-search-results" aria-label="历史搜索结果">
              {searchConversations.length > 0 ? (
                searchConversations.map((conversation) => (
                  <button
                    className="history-search-result"
                    key={conversation.id}
                    type="button"
                    aria-label={`${conversation.title}，${conversation.meta}`}
                    onClick={() => selectSearchConversation(conversation)}
                  >
                    <ChatCircle size={18} weight="duotone" aria-hidden="true" />
                    <span>
                      <strong>{conversation.title}</strong>
                      <small>{conversation.meta}</small>
                    </span>
                  </button>
                ))
              ) : (
                <p className="history-search-empty">没有匹配的历史对话</p>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
