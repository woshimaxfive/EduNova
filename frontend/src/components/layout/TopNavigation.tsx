import {
  BookOpen,
  Brain,
  ChartLineUp,
  GearSix,
  House,
  MagnifyingGlass,
  Notebook,
  SignOut,
  Sparkle,
  Student,
  UploadSimple,
  UserCircle
} from "@phosphor-icons/react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";
import { useAuthStore } from "../../features/auth/authStore";

const primaryNavItems = [
  { label: "学习空间", to: PATHS.app, icon: House },
  { label: "资料库", to: PATHS.library, icon: BookOpen },
  { label: "资源工坊", to: PATHS.studio, icon: Sparkle }
];

const personalMenuItems = [
  { label: "学习画像", to: PATHS.profile, icon: Brain },
  { label: "学习报告", to: PATHS.reports, icon: ChartLineUp },
  { label: "系统设置", to: PATHS.settings, icon: GearSix }
];

export function TopNavigation() {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const { notice, showNotice } = useActionNotice();

  function logout() {
    clearSession();
    navigate(PATHS.login);
  }

  return (
    <header className="top-navigation">
      <NavLink className="brand-mark" to={PATHS.app} aria-label="EduNova 首页">
        <span className="brand-symbol" aria-hidden="true">
          <Student size={22} weight="duotone" />
        </span>
        <span>EduNova</span>
      </NavLink>
      <nav className="nav-links" aria-label="应用导航">
        {primaryNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === PATHS.app}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              <Icon size={18} weight="duotone" aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="nav-actions">
        <button className="icon-button" type="button" aria-label="搜索" onClick={() => showNotice("全局搜索会在课程与资料索引接入后开放。")}>
          <MagnifyingGlass size={18} />
        </button>
        <NavLink className="icon-button" to={PATHS.library} aria-label="上传资料">
          <UploadSimple size={18} />
        </NavLink>
        <div className="user-menu-shell">
          <button
            className="user-chip"
            type="button"
            aria-label="打开个人菜单"
            aria-haspopup="menu"
            aria-expanded={isUserMenuOpen}
            onClick={() => setIsUserMenuOpen((open) => !open)}
          >
            <UserCircle size={20} weight="duotone" aria-hidden="true" />
            <span className="user-chip-name">{user?.displayName ?? "学生"}</span>
          </button>
          {isUserMenuOpen ? (
            <nav className="user-menu-popover" role="menu" aria-label="个人菜单">
              {personalMenuItems.map((item) => {
                const Icon = item.icon;

                return (
                  <NavLink key={item.to} to={item.to} role="menuitem" onClick={() => setIsUserMenuOpen(false)}>
                    <Icon size={17} weight="duotone" aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          ) : null}
        </div>
        <button className="icon-button" type="button" aria-label="退出登录" onClick={logout}>
          <SignOut size={18} />
        </button>
      </div>
      <ActionNotice notice={notice} className="nav-action-notice" />
      <nav className="mobile-route-strip" aria-label="移动导航">
        {primaryNavItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === PATHS.app}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Notebook className="nav-watermark" size={120} weight="thin" aria-hidden="true" />
    </header>
  );
}
