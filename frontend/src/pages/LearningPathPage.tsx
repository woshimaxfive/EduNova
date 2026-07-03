import { ArrowRight, CheckCircle, Compass, FileText, Sparkle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { PageFrame } from "./PageFrame";

const pathStages = [
  {
    title: "先稳核心概念",
    meta: "今天 · 20 分钟",
    status: "进行中",
    tasks: ["监督学习三要素", "训练集与测试集", "泛化误差"],
    source: "AI 导论讲义 · 第 2 章"
  },
  {
    title: "再补薄弱推导",
    meta: "明天 · 35 分钟",
    status: "待开始",
    tasks: ["链式法则", "计算图局部梯度", "反向传播步骤"],
    source: "期末复习题 2025"
  },
  {
    title: "最后做综合练习",
    meta: "本周 · 2 组题",
    status: "待生成",
    tasks: ["错因回看", "相似题训练", "口头复述"],
    source: "练习记录与错题队列"
  }
];

const pathEvidence = [
  "最近对话集中在神经网络和反向传播。",
  "资料库已包含 AI 导论讲义、期末复习题和课堂截图。",
  "练习记录显示概念判断稳定，推导步骤容易跳步。"
];

export function LearningPathPage() {
  return (
    <PageFrame title="学习路径">
      <div className="student-workspace learning-path-workspace">
        <section className="student-panel path-stage-panel" role="region" aria-label="阶段任务">
          <div className="student-panel-heading">
            <div>
              <h2>阶段任务</h2>
            </div>
            <span className="panel-count">
              <Target size={17} weight="duotone" aria-hidden="true" />
              3 阶段
            </span>
          </div>

          <ol className="path-stage-list">
            {pathStages.map((stage, index) => (
              <li className={index === 0 ? "active" : ""} key={stage.title}>
                <span className="path-stage-index">{index + 1}</span>
                <div className="path-stage-content">
                  <span className="path-stage-meta">{stage.meta}</span>
                  <strong>{stage.title}</strong>
                  <ul>
                    {stage.tasks.map((task) => (
                      <li key={task}>
                        <CheckCircle size={15} weight="duotone" aria-hidden="true" />
                        <span>{task}</span>
                      </li>
                    ))}
                  </ul>
                  <span className="path-stage-source">
                    <FileText size={15} weight="duotone" aria-hidden="true" />
                    {stage.source}
                  </span>
                </div>
                <span className="path-stage-status">{stage.status}</span>
              </li>
            ))}
          </ol>
        </section>

        <aside className="path-side-stack">
          <section className="student-panel path-evidence-panel" role="region" aria-label="路径依据">
            <div className="student-panel-heading compact">
              <div>
                <h2>路径依据</h2>
              </div>
            </div>
            <ul className="path-evidence-list">
              {pathEvidence.map((item) => (
                <li key={item}>
                  <Sparkle size={17} weight="duotone" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="student-panel path-action-panel" role="region" aria-label="下一步行动">
            <Compass size={26} weight="duotone" aria-hidden="true" />
            <div>
              <span className="path-action-eyebrow">下一步行动</span>
              <strong>从当前阶段继续。</strong>
              <p>先完成核心概念复述，再进入练习和报告闭环。</p>
            </div>
            <Link className="primary-action" to={PATHS.practice}>
              <span>开始练习</span>
              <ArrowRight size={17} weight="bold" aria-hidden="true" />
            </Link>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
