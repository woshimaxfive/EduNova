import { ArrowRight, BookOpen, ChatCircleText, FileArrowUp } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

const options = [
  {
    title: "学习数据结构与算法",
    text: "从内置课程的知识点、实验和课程问答开始。",
    to: PATHS.app,
    icon: BookOpen
  },
  {
    title: "上传自己的课程资料",
    text: "PDF、DOCX、PPTX 和文本资料会保留为你的原文件。",
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
