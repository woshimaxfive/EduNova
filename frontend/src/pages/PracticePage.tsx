import { CheckCircle, WarningCircle } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function PracticePage() {
  return (
    <PageFrame kicker="练习评估" title="用题目反推薄弱点" description="作答、批改、错因和复习队列会和知识画布同步。">
      <div className="practice-panel">
        <article>
          <WarningCircle size={22} weight="duotone" />
          <strong>薄弱点：链式法则应用</strong>
          <p>建议先复习计算图，再完成 8 道递进题。</p>
        </article>
        <article>
          <CheckCircle size={22} weight="duotone" />
          <strong>已掌握：人工智能概述</strong>
          <p>可以进入搜索和知识表示章节。</p>
        </article>
      </div>
    </PageFrame>
  );
}
