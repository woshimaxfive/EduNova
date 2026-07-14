import { ArrowRight, BookOpen, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { getApiErrorMessage } from "../api/errors";
import { PATHS } from "../app/routePaths";
import { mapApiUserToStudentUser } from "../features/auth/authMappers";
import { useAuthStore } from "../features/auth/authStore";

type LocationState = {
  from?: {
    pathname?: string;
  };
  notice?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formMessage, setFormMessage] = useState("");
  const locationState = location.state as LocationState | null;
  const from = locationState?.from?.pathname ?? PATHS.app;
  const notice = locationState?.notice;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormMessage("");
    setIsSubmitting(true);

    try {
      const response = await login({ email, password });
      setSession({
        token: response.data.access_token,
        user: mapApiUserToStudentUser(response.data.user)
      });
      navigate(from, { replace: true });
    } catch (error) {
      setFormMessage(getApiErrorMessage(error, "登录失败，请检查邮箱和密码。"));
    } finally {
      setIsSubmitting(false);
    }
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
          <span>数据结构与算法内置课程会复制到个人空间，学习记录彼此独立。</span>
        </div>
      </section>
      <section className="entry-panel" aria-label="登录">
        <p className="section-kicker">学生入口</p>
        <h1>进入你的学习空间</h1>
        <p>继续使用自己的资料、课程和对话。新账号可以空白开始，也可以加入数据结构与算法内置课程。</p>
        <form className="entry-form" onSubmit={handleSubmit}>
          {notice ? <p className="form-info">{notice}</p> : null}
          {formMessage ? <p className="form-error" role="alert">{formMessage}</p> : null}
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
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            <span>{isSubmitting ? "登录中" : "登录"}</span>
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
