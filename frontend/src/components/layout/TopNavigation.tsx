import {
  BookOpen,
  Brain,
  ChartLineUp,
  ChatCircleText,
  GearSix,
  House,
  ListChecks,
  MagnifyingGlass,
  Notebook,
  SignOut,
  Sparkle,
  Student,
  UploadSimple,
  UserCircle
} from "@phosphor-icons/react";
import { NavLink, useNavigate } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";
import { useAuthStore } from "../../features/auth/authStore";

const navItems = [
  { label: "学习空间", to: PATHS.app, icon: House },
  { label: "资料库", to: PATHS.library, icon: BookOpen },
  { label: "Studio", to: PATHS.studio, icon: Sparkle },
  { label: "画像", to: PATHS.profile, icon: Brain },
  { label: "辅导", to: PATHS.tutor, icon: ChatCircleText },
  { label: "练习", to: PATHS.practice, icon: ListChecks },
  { label: "报告", to: PATHS.reports, icon: ChartLineUp },
  { label: "设置", to: PATHS.settings, icon: GearSix }
];

export function TopNavigation() {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);
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
        {navItems.map((item) => {
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
        <div className="user-chip" aria-label="当前用户">
          <UserCircle size={20} weight="duotone" aria-hidden="true" />
          <span>{user?.displayName ?? "学生"}</span>
        </div>
        <button className="icon-button" type="button" aria-label="退出登录" onClick={logout}>
          <SignOut size={18} />
        </button>
      </div>
      <ActionNotice notice={notice} className="nav-action-notice" />
      <nav className="mobile-route-strip" aria-label="移动导航">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === PATHS.app}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Notebook className="nav-watermark" size={120} weight="thin" aria-hidden="true" />
    </header>
  );
}
