import { ArrowRight } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { getApiErrorMessage } from "../api/errors";
import { PATHS } from "../app/routePaths";
import { AuthShell } from "../components/auth/AuthShell";
import { PasswordField } from "../components/auth/PasswordField";
import { mapApiUserToStudentUser } from "../features/auth/authMappers";
import { useAuthStore } from "../features/auth/authStore";
import "../styles/auth.css";

type LocationState = {
  from?: { pathname?: string };
  notice?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formMessage, setFormMessage] = useState("");
  const locationState = location.state as LocationState | null;
  const from = locationState?.from?.pathname ?? PATHS.app;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormMessage("");
    setIsSubmitting(true);

    try {
      const response = await login({ account: account.trim().toLowerCase(), password });
      setSession({ token: response.data.access_token, user: mapApiUserToStudentUser(response.data.user) });
      navigate(from, { replace: true });
    } catch (error) {
      setFormMessage(getApiErrorMessage(error, "登录失败，请检查账号和密码。"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell mode="login">
      <div className="auth-form-heading">
        <h1>登录</h1>
        <p>使用 EduNova 账号继续。</p>
      </div>
      <form className="auth-form" onSubmit={handleSubmit}>
        {locationState?.notice ? <p className="auth-feedback info">{locationState.notice}</p> : null}
        {formMessage ? <p className="auth-feedback error" role="alert">{formMessage}</p> : null}
        <label className="auth-field">
          <span>账号</span>
          <input
            value={account}
            onChange={(event) => setAccount(event.target.value)}
            onBlur={() => setAccount((current) => current.trim().toLowerCase())}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
          />
        </label>
        <PasswordField label="密码" value={password} onChange={setPassword} autoComplete="current-password" />
        <button className="auth-primary-action" type="submit" disabled={isSubmitting || !account.trim() || !password}>
          <span>{isSubmitting ? "正在登录" : "登录"}</span>
          <ArrowRight size={19} aria-hidden="true" />
        </button>
      </form>
      <p className="auth-switch">还没有账号？ <Link to={PATHS.register}>创建账号</Link></p>
    </AuthShell>
  );
}
