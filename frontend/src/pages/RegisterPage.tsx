import { ArrowRight, Sparkle } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";

export function RegisterPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const [nickname, setNickname] = useState("我的学习账号");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
        role: "student"
      }
    });
    navigate(PATHS.app, { replace: true });
  }

  return (
    <main className="entry-page register-entry">
      <div className="ambient-layer" aria-hidden="true" />
      <section className="entry-panel compact" aria-label="注册">
        <div className="brand-mark entry-brand">
          <Sparkle size={22} weight="duotone" aria-hidden="true" />
          <span>EduNova</span>
        </div>
        <p className="section-kicker">创建账号</p>
        <h1>准备你的学习空间</h1>
        <p>账号只保存必要信息，学习画像会在首次进入后通过对话建立。</p>
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
