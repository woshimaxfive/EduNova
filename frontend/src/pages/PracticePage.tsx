import { CheckCircle, ListChecks, WarningCircle } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

const reviewItems = ["链式法则应用", "计算图局部梯度", "反向传播步骤表达"];

export function PracticePage() {
  const [answer, setAnswer] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [attemptCount, setAttemptCount] = useState(0);
  const { notice, showNotice } = useActionNotice();

  function submitAnswer() {
    if (!answer.trim()) {
      showNotice("先写下你的推导思路。", "warning");
      return;
    }

    setHasSubmitted(true);
    setAttemptCount((current) => current + 1);
    showNotice("已提交答案。", "success");
  }

  return (
    <PageFrame title="练习">
      <div className="student-workspace practice-workspace">
        <section className="student-panel practice-question" role="region" aria-label="练习作答">
          <div className="student-panel-heading">
            <div>
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
            <textarea
              rows={5}
              aria-label="作答区"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="写下你的推导过程。"
            />
          </label>
          <button className="primary-action" type="button" onClick={submitAnswer}>
            提交答案
          </button>
          <ActionNotice notice={notice} />
        </section>

        <aside className="practice-side-stack">
          <section className="student-panel feedback-panel" role="region" aria-label="批改反馈">
            <div className="feedback-status">
              <WarningCircle size={22} weight="duotone" aria-hidden="true" />
              <span>
                <strong>{hasSubmitted ? "本次批改：关键概念已覆盖" : "薄弱点：链式法则应用"}</strong>
                <small>{hasSubmitted ? "还需要补一句“复合函数对参数的影响由局部梯度相乘得到”。" : "建议先复习计算图，再完成 8 道递进题。"}</small>
              </span>
            </div>
            <div className="feedback-status mastered">
              <CheckCircle size={22} weight="duotone" aria-hidden="true" />
              <span>
                <strong>已掌握：人工智能概述</strong>
                <small>{hasSubmitted ? `已记录第 ${attemptCount} 次作答。` : "可以进入搜索和知识表示章节。"}</small>
              </span>
            </div>
          </section>

          <section className="student-panel review-queue" role="region" aria-label="薄弱点复习队列">
            <div className="student-panel-heading compact">
              <div>
                <h2>下一组复习</h2>
              </div>
            </div>
            <ol>
              {reviewItems.map((item, index) => (
                <li className={hasSubmitted && index === 0 ? "active" : ""} key={item}>
                  <ListChecks size={17} weight="duotone" aria-hidden="true" />
                  <span>{hasSubmitted && index === 0 ? `${item} · 下一题` : item}</span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
