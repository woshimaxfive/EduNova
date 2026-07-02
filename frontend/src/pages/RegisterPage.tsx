import { ArrowRight, BookOpen, Sparkle, UploadSimple } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";

type StarterMode = "blank" | "ai_intro";

export function RegisterPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const [nickname, setNickname] = useState("我的学习账号");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [starterMode, setStarterMode] = useState<StarterMode>("ai_intro");
  const passwordMismatch = Boolean(confirmPassword && password !== confirmPassword);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (passwordMismatch) return;
    setSession({
      token: "local-register-preview-token",
      user: {
        id: 2,
        email: email || "student@edunova.local",
        displayName: nickname,
        role: "student",
        starterMode
      }
    });
    navigate(PATHS.app, { replace: true });
  }

  return (
    <main className="entry-page register-entry auth-entry-page">
      <div className="ambient-layer" aria-hidden="true" />
      <section className="entry-panel compact" aria-label="注册">
        <div className="brand-mark entry-brand">
          <Sparkle size={22} weight="duotone" aria-hidden="true" />
          <span>EduNova</span>
        </div>
        <p className="section-kicker">创建账号</p>
        <h1>准备你的学习空间</h1>
        <p>先决定这个账号从哪里开始：空白上传自己的资料，或者复制一门人工智能导论示例课程用于体验。</p>
        <form className="entry-form" onSubmit={handleSubmit}>
          <label>
            昵称
            <input value={nickname} onChange={(event) => setNickname(event.target.value)} autoComplete="nickname" />
          </label>
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
              autoComplete="new-password"
            />
          </label>
          <label>
            确认密码
            <input
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              type="password"
              autoComplete="new-password"
              aria-invalid={passwordMismatch}
            />
          </label>
          {passwordMismatch ? <p className="form-error">两次输入的密码不一致。</p> : null}
          <fieldset className="starter-mode-group">
            <legend>创建方式</legend>
            <label className={starterMode === "blank" ? "starter-mode-option active" : "starter-mode-option"}>
              <input
                type="radio"
                name="starterMode"
                value="blank"
                checked={starterMode === "blank"}
                onChange={() => setStarterMode("blank")}
              />
              <span className="starter-mode-icon" aria-hidden="true">
                <UploadSimple size={18} weight="duotone" />
              </span>
              <span>
                <strong>空白开始</strong>
                <small>进入后没有课程和资料，从自己的文件开始。</small>
              </span>
            </label>
            <label className={starterMode === "ai_intro" ? "starter-mode-option active" : "starter-mode-option"}>
              <input
                type="radio"
                name="starterMode"
                value="ai_intro"
                checked={starterMode === "ai_intro"}
                onChange={() => setStarterMode("ai_intro")}
              />
              <span className="starter-mode-icon" aria-hidden="true">
                <BookOpen size={18} weight="duotone" />
              </span>
              <span>
                <strong>带一个示例课程开始</strong>
                <small>复制「人工智能导论」到你的空间，用于快速体验完整学习闭环。</small>
              </span>
            </label>
          </fieldset>
          <label className="check-row">
            <input type="checkbox" defaultChecked />
            <span>我了解上传资料会用于构建个人学习空间</span>
          </label>
          <button className="primary-button" type="submit" disabled={passwordMismatch}>
            <span>创建并进入</span>
            <ArrowRight size={18} aria-hidden="true" />
          </button>
        </form>
        <p className="entry-switch">
          已有账号？ <Link to={PATHS.login}>回到登录</Link>
        </p>
      </section>
    </main>
  );
}
