import { PlayCircle } from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { startDemoSession } from "../features/demo/demoApi";
import { useAuthStore } from "../features/auth/authStore";

export function DemoEntryPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const [isLoading, setIsLoading] = useState(false);

  async function start() {
    setIsLoading(true);
    const session = await startDemoSession();
    setSession(session);
    navigate(PATHS.app, { replace: true });
  }

  return (
    <main className="entry-page demo-entry">
      <section className="entry-panel compact">
        <p className="section-kicker">Demo Mode</p>
        <h1>准备演示学习空间</h1>
        <p>演示账号会进入人工智能导论课程，并使用明确标记的样例数据。</p>
        <button className="primary-button" type="button" onClick={start} disabled={isLoading}>
          <PlayCircle size={20} weight="duotone" aria-hidden="true" />
          <span>{isLoading ? "正在初始化" : "进入演示"}</span>
        </button>
      </section>
    </main>
  );
}
