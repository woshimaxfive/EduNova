import { ChartLineUp, FileArrowUp } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function ReportsPage() {
  return (
    <PageFrame kicker="学习报告" title="让推荐原因可解释" description="掌握度、画像变化、错因和 Agent 证据会进入学习档案。">
      <div className="report-panel">
        <ChartLineUp size={26} weight="duotone" aria-hidden="true" />
        <div>
          <strong>本周掌握度正在生成</strong>
          <p>报告页会承接 ECharts 掌握度图和 Markdown 学习档案导出。</p>
        </div>
        <button className="soft-button" type="button">
          <FileArrowUp size={17} aria-hidden="true" />
          <span>导出档案</span>
        </button>
      </div>
    </PageFrame>
  );
}
