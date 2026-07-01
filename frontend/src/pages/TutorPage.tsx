import { ChatCircleText, ShieldCheck } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function TutorPage() {
  return (
    <PageFrame kicker="AI 辅导" title="围绕课程资料追问" description="直接解释、苏格拉底追问和考前冲刺会共用同一套引用机制。">
      <div className="tutor-shell">
        <div className="message user">为什么反向传播需要链式法则？</div>
        <div className="message assistant">
          <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
          <span>因为每一层参数对最终损失的影响都要沿计算图逐层传回。</span>
        </div>
        <div className="evidence-tag">
          <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
          <span>回答将绑定课程引用</span>
        </div>
      </div>
    </PageFrame>
  );
}
