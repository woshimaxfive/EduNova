import { Link } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";

export function NotFoundPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return (
    <main className="state-page">
      <section className="state-panel">
        <p className="section-kicker">404</p>
        <h1>没有找到这个学习入口</h1>
        <p>当前地址没有匹配到 EduNova 的页面。</p>
        <Link className="primary-button" to={isAuthenticated ? PATHS.app : PATHS.login}>
          回到{isAuthenticated ? "学习空间" : "登录页"}
        </Link>
      </section>
    </main>
  );
}
