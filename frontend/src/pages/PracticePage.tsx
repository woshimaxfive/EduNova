import { CheckCircle, ListChecks, WarningCircle } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

const reviewItems = ["链式法则应用", "计算图局部梯度", "反向传播步骤表达"];

export function PracticePage() {
  return (
    <PageFrame kicker="练习评估" title="用题目反推薄弱点" description="作答、批改、错因和复习队列会和知识画布同步。">
      <div className="student-workspace practice-workspace">
        <section className="student-panel practice-question" role="region" aria-label="练习作答">
          <div className="student-panel-heading">
            <div>
              <p className="section-kicker">Practice</p>
              <h2>递进题 1 / 8</h2>
            </div>
            <span className="panel-count">监督学习</span>
          </div>
          <article className="question-block">
            <strong>给定损失函数 L=f(g(w))，为什么更新 w 时需要链式法则？</strong>
            <p>请用“局部梯度”和“影响如何传回参数”两个关键词解释。</p>
          </article>
          <label className="answer-box">
            <span>作答区</span>
            <textarea rows={5} placeholder="写下你的推导过程，系统会先看思路再给答案。" />
          </label>
          <button className="primary-action" type="button">提交答案</button>
        </section>

        <aside className="practice-side-stack">
          <section className="student-panel feedback-panel" role="region" aria-label="批改反馈">
            <div className="feedback-status">
              <WarningCircle size={22} weight="duotone" aria-hidden="true" />
              <span>
                <strong>薄弱点：链式法则应用</strong>
                <small>建议先复习计算图，再完成 8 道递进题。</small>
              </span>
            </div>
            <div className="feedback-status mastered">
              <CheckCircle size={22} weight="duotone" aria-hidden="true" />
              <span>
                <strong>已掌握：人工智能概述</strong>
                <small>可以进入搜索和知识表示章节。</small>
              </span>
            </div>
          </section>

          <section className="student-panel review-queue" role="region" aria-label="薄弱点复习队列">
            <div className="student-panel-heading compact">
              <div>
                <p className="section-kicker">Review</p>
                <h2>下一组复习</h2>
              </div>
            </div>
            <ol>
              {reviewItems.map((item) => (
                <li key={item}>
                  <ListChecks size={17} weight="duotone" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
