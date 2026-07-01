import { Brain, ChatCircleText, Compass, PencilSimpleLine, TrendUp } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

const profileDimensions = [
  { label: "目标", value: "两周内完成期末复习路线", tone: "focus" },
  { label: "基础", value: "搜索与机器学习概念较稳", tone: "ready" },
  { label: "薄弱点", value: "反向传播链式法则", tone: "warning" },
  { label: "节奏", value: "每天 45 分钟，偏好短讲解加练习", tone: "steady" }
];

const evidenceItems = ["最近 3 次追问集中在神经网络", "错题反馈显示推导步骤容易跳步", "上传资料覆盖监督学习和期末题"];

export function ProfilePage() {
  return (
    <PageFrame kicker="对话画像" title="用聊天建立学习画像" description="目标、基础、偏好、薄弱点和学习节奏会随着证据持续更新。">
      <div className="student-workspace profile-workspace">
        <section className="student-panel profile-summary" role="region" aria-label="学习画像">
          <div className="student-panel-heading">
            <div>
              <p className="section-kicker">Profile</p>
              <h2>当前画像</h2>
            </div>
            <span className="profile-score">
              <TrendUp size={17} weight="duotone" aria-hidden="true" />
              可信度 72%
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
          <button className="soft-button" type="button">
            <PencilSimpleLine size={17} weight="duotone" aria-hidden="true" />
            <span>更新目标</span>
          </button>
        </section>

        <aside className="profile-side-stack">
          <section className="student-panel evidence-summary" role="region" aria-label="画像证据">
            <div className="student-panel-heading compact">
              <div>
                <p className="section-kicker">Evidence</p>
                <h2>为什么这样判断</h2>
              </div>
            </div>
            <ul className="evidence-list">
              {evidenceItems.map((item) => (
                <li key={item}>
                  <Brain size={17} weight="duotone" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="student-panel profile-dialog-entry" role="region" aria-label="画像对话入口">
            <ChatCircleText size={24} weight="duotone" aria-hidden="true" />
            <div>
              <strong>先问 2 到 3 个问题，再生成初始画像。</strong>
              <p>后续练习和错因会继续修正画像，不需要一次性填完问卷。</p>
            </div>
            <div className="profile-prompt-strip">
              <Compass size={17} weight="duotone" aria-hidden="true" />
              <span>下一问：这门课你最担心哪一章？</span>
            </div>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
