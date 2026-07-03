import { ArrowRight, BookOpen, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const from = (location.state as LocationState | null)?.from?.pathname ?? PATHS.app;

  function completeLogin() {
    setSession({
      token: "local-preview-token",
      user: {
        id: 1,
        email,
        displayName: "演示学生",
        role: "student",
        starterMode: "ai_intro"
      }
    });
    navigate(from, { replace: true });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    completeLogin();
  }

  return (
    <main className="entry-page auth-entry-page">
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
          <span>登录只回到你的学习空间。是否带示例课程，由注册时自己选择。</span>
        </div>
        <div className="preview-note secondary">
          <BookOpen size={22} weight="duotone" aria-hidden="true" />
          <span>人工智能导论示例课程会作为可复制模板，不与其他用户共享修改。</span>
        </div>
      </section>
      <section className="entry-panel" aria-label="登录">
        <p className="section-kicker">学生入口</p>
        <h1>进入你的学习空间</h1>
        <p>继续使用自己的资料、课程和对话。新账号可以在注册时选择空白开始，或带一门人工智能导论示例课程。</p>
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
        <p className="entry-switch">
          还没有账号？ <Link to={PATHS.register}>创建学生账号</Link>
        </p>
      </section>
    </main>
  );
}
