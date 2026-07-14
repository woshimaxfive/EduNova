import { Student } from "@phosphor-icons/react";
import { type ReactNode } from "react";

import { AuthProductPreview } from "./AuthProductPreview";

type AuthShellProps = {
  children: ReactNode;
  mode: "login" | "register";
};

export function AuthShell({ children, mode }: AuthShellProps) {
  return (
    <main className="auth-shell">
      <section className="auth-product-side" aria-label="EduNova 产品预览">
        <header className="auth-brand-row">
          <div className="auth-brand">
            <span className="auth-brand-symbol" aria-hidden="true">
              <Student size={23} weight="duotone" />
            </span>
            <span>EduNova</span>
          </div>
          <p>你的个人学习空间</p>
        </header>
        <AuthProductPreview />
      </section>

      <section className="auth-form-side" aria-label={mode === "login" ? "登录" : "注册"}>
        <div className="auth-mobile-brand" aria-hidden="true">
          <span className="auth-brand-symbol">
            <Student size={21} weight="duotone" />
          </span>
          <span>EduNova</span>
        </div>
        <div className="auth-form-wrap">{children}</div>
      </section>
    </main>
  );
}
