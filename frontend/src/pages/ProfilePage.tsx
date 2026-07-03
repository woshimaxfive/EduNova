import { Brain, ChatCircleText, Compass, PencilSimpleLine, TrendUp } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

const initialProfileDimensions = [
  { label: "目标", value: "两周内完成期末复习路线", tone: "focus" },
  { label: "基础", value: "搜索与机器学习概念较稳", tone: "ready" },
  { label: "薄弱点", value: "反向传播链式法则", tone: "warning" },
  { label: "节奏", value: "每天 45 分钟，偏好短讲解加练习", tone: "steady" }
];

const evidenceItems = ["最近 3 次追问集中在神经网络", "错题反馈显示推导步骤容易跳步", "上传资料覆盖监督学习和期末题"];

export function ProfilePage() {
  const [profileDimensions, setProfileDimensions] = useState(initialProfileDimensions);
  const [profileEvidence, setProfileEvidence] = useState(evidenceItems);
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [goalDraft, setGoalDraft] = useState(initialProfileDimensions[0].value);
  const [profileAnswer, setProfileAnswer] = useState("");
  const [confidence, setConfidence] = useState(72);
  const { notice, showNotice } = useActionNotice();

  function saveGoal() {
    const nextGoal = goalDraft.trim();

    if (!nextGoal) {
      showNotice("先写下新的学习目标。", "warning");
      return;
    }

    setProfileDimensions((current) => current.map((item) => (item.label === "目标" ? { ...item, value: nextGoal } : item)));
    setProfileEvidence((current) => [`目标更新：${nextGoal}`, ...current]);
    setConfidence((current) => Math.min(current + 3, 92));
    setIsEditingGoal(false);
    showNotice("学习目标已更新。", "success");
  }

  function submitProfileAnswer() {
    const answer = profileAnswer.trim();

    if (!answer) {
      showNotice("先回答一个画像问题。", "warning");
      return;
    }

    setProfileEvidence((current) => [`画像对话：${answer}`, ...current]);
    setConfidence((current) => Math.min(current + 4, 94));
    setProfileAnswer("");
    showNotice("画像证据已更新。", "success");
  }

  return (
    <PageFrame title="学习画像">
      <div className="student-workspace profile-workspace">
        <section className="student-panel profile-summary" role="region" aria-label="学习画像">
          <div className="student-panel-heading">
            <div>
              <h2>当前画像</h2>
            </div>
            <span className="profile-score">
              <TrendUp size={17} weight="duotone" aria-hidden="true" />
              可信度 {confidence}%
            </span>
          </div>
          <div className="profile-dimension-grid">
            {profileDimensions.map((item) => (
              <article className={`profile-dimension ${item.tone}`} key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </article>
            ))}
          </div>
          {isEditingGoal ? (
            <div className="inline-edit-row">
              <input aria-label="学习目标" value={goalDraft} onChange={(event) => setGoalDraft(event.target.value)} />
              <button className="primary-action" type="button" onClick={saveGoal}>
                保存目标
              </button>
            </div>
          ) : null}
          <button className="soft-button" type="button" onClick={() => setIsEditingGoal((editing) => !editing)}>
            <PencilSimpleLine size={17} weight="duotone" aria-hidden="true" />
            <span>更新目标</span>
          </button>
          <ActionNotice notice={notice} />
        </section>

        <aside className="profile-side-stack">
          <section className="student-panel evidence-summary" role="region" aria-label="画像证据">
            <div className="student-panel-heading compact">
              <div>
                <h2>判断依据</h2>
              </div>
            </div>
            <ul className="evidence-list">
              {profileEvidence.map((item, index) => (
                <li key={`${item}-${index}`}>
                  <Brain size={17} weight="duotone" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="student-panel profile-dialog-entry" role="region" aria-label="画像对话入口">
            <ChatCircleText size={24} weight="duotone" aria-hidden="true" />
            <div>
              <strong>回答几个问题，生成初始画像。</strong>
              <p>练习和错因会持续修正画像。</p>
            </div>
            <div className="profile-prompt-strip">
              <Compass size={17} weight="duotone" aria-hidden="true" />
              <span>下一问：这门课你最担心哪一章？</span>
            </div>
            <label className="profile-answer-box">
              <span>我的回答</span>
              <textarea
                rows={3}
                value={profileAnswer}
                aria-label="画像问题回答"
                onChange={(event) => setProfileAnswer(event.target.value)}
                placeholder="比如：最担心反向传播推导。"
              />
            </label>
            <button className="primary-action" type="button" onClick={submitProfileAnswer}>
              更新画像
            </button>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
