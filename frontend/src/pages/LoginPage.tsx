import { ArrowRight, PlayCircle, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { startDemoSession } from "../features/demo/demoApi";
import { useAuthStore } from "../features/auth/authStore";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [email, setEmail] = useState("demo@edunova.local");
  const [password, setPassword] = useState("Demo123456");
  const [isPreparingDemo, setIsPreparingDemo] = useState(false);
  const from = (location.state as LocationState | null)?.from?.pathname ?? PATHS.app;

  function completeLogin() {
    setSession({
      token: "local-preview-token",
      user: {
        id: 1,
        email,
        displayName: "演示学生",
        role: "student"
      }
    });
    navigate(from, { replace: true });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    completeLogin();
  }

  async function handleDemo() {
    setIsPreparingDemo(true);
    const session = await startDemoSession();
    setSession(session);
    navigate(PATHS.app, { replace: true });
  }

  return (
    <main className="entry-page">
      <div className="ambient-layer" aria-hidden="true" />
      <section className="entry-preview" aria-label="学习空间预览">
        <div className="brand-mark entry-brand">
          <Sparkle size={22} weight="duotone" aria-hidden="true" />
          <span>EduNova</span>
        </div>
        <div className="preview-canvas">
          <span className="preview-node focus">监督学习</span>
          <span className="preview-node">搜索</span>
          <span className="preview-node weak">神经网络</span>
          <span className="preview-thread" />
        </div>
        <div className="preview-note">
          <ShieldCheck size={22} weight="duotone" aria-hidden="true" />
          <span>引用、Agent 轨迹和资源审核会在学习时一起留下证据。</span>
        </div>
      </section>
      <section className="entry-panel" aria-label="登录">
        <p className="section-kicker">学生入口</p>
        <h1>进入你的 AI 学习空间</h1>
        <p>把课程资料、知识路径、练习评估和 AI 辅导放在同一个学习空间里。</p>
        <form className="entry-form" onSubmit={handleSubmit}>
          <label>
            邮箱
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" />
          </label>
          <label>
            密码
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </label>
          <label className="check-row">
            <input type="checkbox" defaultChecked />
            <span>记住登录状态</span>
          </label>
          <button className="primary-button" type="submit">
            <span>登录</span>
            <ArrowRight size={18} aria-hidden="true" />
          </button>
        </form>
        <button className="demo-button" type="button" onClick={handleDemo} disabled={isPreparingDemo}>
          <PlayCircle size={20} weight="duotone" aria-hidden="true" />
          <span>{isPreparingDemo ? "正在准备演示学习空间" : "体验演示学生"}</span>
        </button>
        <p className="entry-switch">
          还没有账号？ <Link to={PATHS.register}>创建学生账号</Link>
        </p>
      </section>
    </main>
  );
}
