import { ArrowRight, BookOpen, UploadSimple } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { login, register } from "../api/auth";
import { getApiErrorMessage } from "../api/errors";
import { PATHS } from "../app/routePaths";
import { AuthShell } from "../components/auth/AuthShell";
import { PasswordField } from "../components/auth/PasswordField";
import { mapApiUserToStudentUser } from "../features/auth/authMappers";
import { useAuthStore } from "../features/auth/authStore";
import "../styles/auth.css";

type StarterMode = "blank" | "data_structures";

export function RegisterPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const [displayName, setDisplayName] = useState("");
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [starterMode, setStarterMode] = useState<StarterMode>("blank");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const passwordMismatch = Boolean(confirmPassword && password !== confirmPassword);
  const normalizedAccount = account.trim().toLowerCase();
  const accountValid = /^[a-z0-9][a-z0-9_]{3,23}$/.test(normalizedAccount);
  const passwordValid = password.length >= 8 && /[A-Za-z]/.test(password) && /\d/.test(password);
  const formValid = Boolean(displayName.trim() && accountValid && passwordValid && confirmPassword && !passwordMismatch);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formValid) return;
    setFormError("");
    setIsSubmitting(true);

    try {
      await register({ account: normalizedAccount, password, display_name: displayName.trim(), starter_mode: starterMode });
    } catch (error) {
      setFormError(getApiErrorMessage(error, "账号创建失败，请检查填写内容。"));
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await login({ account: normalizedAccount, password });
      setSession({ token: response.data.access_token, user: mapApiUserToStudentUser(response.data.user) });
      navigate(PATHS.app, { replace: true });
    } catch {
      navigate(PATHS.login, {
        replace: true,
        state: { notice: "账号已创建，请重新登录。" }
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell mode="register">
      <div className="auth-form-heading">
        <h1>创建账号</h1>
        <p>账号用于登录，昵称用于学习空间展示。</p>
      </div>
      <form className="auth-form auth-register-form" onSubmit={handleSubmit}>
        {formError ? <p className="auth-feedback error" role="alert">{formError}</p> : null}
        <label className="auth-field">
          <span>账号</span>
          <input
            value={account}
            onChange={(event) => setAccount(event.target.value)}
            onBlur={() => setAccount(normalizedAccount)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            aria-describedby="account-help"
            aria-invalid={Boolean(account && !accountValid)}
            required
          />
        </label>
        <small id="account-help" className={account && !accountValid ? "auth-help error" : "auth-help"}>
          4–24 位字母、数字或下划线，不区分大小写。
        </small>
        <label className="auth-field">
          <span>昵称</span>
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="nickname" required />
        </label>
        <PasswordField label="密码" value={password} onChange={setPassword} autoComplete="new-password" invalid={Boolean(password && !passwordValid)} />
        <small className={password && !passwordValid ? "auth-help error" : "auth-help"}>至少 8 位，同时包含字母和数字。</small>
        <PasswordField label="确认密码" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" invalid={passwordMismatch} />
        {passwordMismatch ? <p className="auth-feedback error compact" role="alert">两次输入的密码不一致。</p> : null}

        <fieldset className="auth-starter-group">
          <legend>起步内容</legend>
          <div className="auth-starter-options">
            <label className={starterMode === "blank" ? "auth-starter-option active" : "auth-starter-option"}>
              <input type="radio" name="starterMode" value="blank" checked={starterMode === "blank"} onChange={() => setStarterMode("blank")} />
              <UploadSimple size={20} weight="duotone" aria-hidden="true" />
              <span><strong>空白开始</strong><small>从自己的资料开始</small></span>
            </label>
            <label className={starterMode === "data_structures" ? "auth-starter-option active" : "auth-starter-option"}>
              <input type="radio" name="starterMode" value="data_structures" checked={starterMode === "data_structures"} onChange={() => setStarterMode("data_structures")} />
              <BookOpen size={20} weight="duotone" aria-hidden="true" />
              <span><strong>数据结构与算法</strong><small>54 个知识点 · 16 个实验</small></span>
            </label>
          </div>
        </fieldset>

        <button className="auth-primary-action" type="submit" disabled={!formValid || isSubmitting}>
          <span>{isSubmitting ? "正在创建" : "创建并进入"}</span>
          <ArrowRight size={19} aria-hidden="true" />
        </button>
      </form>
      <p className="auth-switch">已有账号？ <Link to={PATHS.login}>返回登录</Link></p>
    </AuthShell>
  );
}
