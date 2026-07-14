import { BookOpen, CheckCircle, FileText, Flask, Student, Target } from "@phosphor-icons/react";
import { type CSSProperties, type ReactNode } from "react";

type AuthShellProps = {
  children: ReactNode;
  mode: "login" | "register";
  starterMode?: "blank" | "data_structures";
};

const loopSteps = [
  { label: "资料", icon: FileText, className: "source" },
  { label: "课程", icon: BookOpen, className: "course" },
  { label: "理解", icon: Target, className: "understand" },
  { label: "练习", icon: Flask, className: "practice" },
  { label: "掌握", icon: CheckCircle, className: "mastery" }
] as const;

export function AuthShell({ children, mode, starterMode = "blank" }: AuthShellProps) {
  const dataStructuresSelected = mode === "register" && starterMode === "data_structures";

  return (
    <main className="auth-shell">
      <section className="auth-visual" aria-label="EduNova 学习闭环预览">
        <div className="auth-visual-grid" aria-hidden="true" />
        <header className="auth-visual-header">
          <div className="auth-brand">
            <span className="auth-brand-symbol" aria-hidden="true">
              <Student size={24} weight="duotone" />
            </span>
            <span>EduNova</span>
          </div>
          <p>让每一份资料，都能走向真正的理解。</p>
        </header>

        <div className="auth-learning-scene" data-starter={dataStructuresSelected ? "course" : "blank"}>
          <div className="auth-scene-copy">
            <span>{dataStructuresSelected ? "内置课程预览" : "个性化学习闭环"}</span>
            <h2>{dataStructuresSelected ? "数据结构与算法" : "从资料到掌握，持续向前"}</h2>
            <p>
              {dataStructuresSelected
                ? "54 个知识点与 16 个 Python 实验，进入后形成你的独立学习记录。"
                : "围绕你的目标、薄弱点和学习证据，组织课程、资源、练习与报告。"}
            </p>
          </div>

          <div className="auth-loop-map" aria-label="资料、课程、理解、练习、掌握">
            <svg className="auth-loop-lines" viewBox="0 0 680 360" role="presentation" aria-hidden="true">
              <path d="M88 238 C154 82 300 56 377 145 S522 294 605 182" />
              <path className="auth-loop-line-accent" d="M88 238 C154 82 300 56 377 145 S522 294 605 182" />
            </svg>
            {loopSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <div key={step.label} className={`auth-loop-node ${step.className}`} style={{ "--node-order": index } as CSSProperties}>
                  <span aria-hidden="true"><Icon size={20} weight="duotone" /></span>
                  <strong>{step.label}</strong>
                </div>
              );
            })}
            <div className="auth-focus-note">
              <span>{dataStructuresSelected ? "当前课程" : "学习依据"}</span>
              <strong>{dataStructuresSelected ? "图的遍历与搜索" : "真实资料 · 真实进展"}</strong>
            </div>
          </div>
        </div>

        <footer className="auth-visual-footer">
          <span>画像</span>
          <span>检索</span>
          <span>辅导</span>
          <span>资源</span>
          <span>评估</span>
          <span>报告</span>
        </footer>
      </section>
      <section className="auth-form-side" aria-label={mode === "login" ? "登录" : "注册"}>
        <div className="auth-form-wrap">{children}</div>
      </section>
    </main>
  );
}
