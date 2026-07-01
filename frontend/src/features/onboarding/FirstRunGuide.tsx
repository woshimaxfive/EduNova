import { ArrowRight, BookOpen, ChatCircleText, FileArrowUp } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

const options = [
  {
    title: "从人工智能导论开始",
    text: "使用内置课程进入完整学习闭环。",
    to: PATHS.app,
    icon: BookOpen
  },
  {
    title: "上传自己的课程资料",
    text: "PPT、PDF、电子书和期末题会进入资料库。",
    to: PATHS.library,
    icon: FileArrowUp
  },
  {
    title: "先建立学习画像",
    text: "用几轮对话告诉 EduNova 你的目标和薄弱点。",
    to: PATHS.profile,
    icon: ChatCircleText
  }
];

export function FirstRunGuide() {
  return (
    <section className="first-run-panel" aria-label="首次进入引导">
      <div>
        <p className="section-kicker">开始方式</p>
        <h2>把今天的学习上下文先放进来</h2>
      </div>
      <div className="first-run-options">
        {options.map((option) => {
          const Icon = option.icon;
          return (
            <Link key={option.title} className="first-run-option" to={option.to}>
              <span className="option-icon" aria-hidden="true">
                <Icon size={20} weight="duotone" />
              </span>
              <span>
                <strong>{option.title}</strong>
                <small>{option.text}</small>
              </span>
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
