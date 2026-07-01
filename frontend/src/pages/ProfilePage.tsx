import { ChatCircleText } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function ProfilePage() {
  return (
    <PageFrame kicker="对话画像" title="用聊天建立学习画像" description="目标、基础、偏好、薄弱点和学习节奏会随着证据持续更新。">
      <div className="chat-panel">
        <ChatCircleText size={24} weight="duotone" aria-hidden="true" />
        <strong>EduNova 会先问 2 到 3 个问题，再生成初始画像。</strong>
        <p>后续练习和错因会继续修正画像，不需要一次性填完问卷。</p>
      </div>
    </PageFrame>
  );
}
