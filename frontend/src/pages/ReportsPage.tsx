import { ChartLineUp, FileArrowUp, FileText, Graph, ShieldCheck } from "@phosphor-icons/react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

const masteryRows = [
  { title: "人工智能概述", value: "已掌握", progress: 88 },
  { title: "监督学习", value: "学习中", progress: 62 },
  { title: "反向传播", value: "薄弱点", progress: 34 }
];

export function ReportsPage() {
  const { notice, showNotice } = useActionNotice();

  return (
    <PageFrame title="让推荐原因可解释" description="掌握度、画像变化、错因和 Agent 证据会进入学习档案。">
      <div className="student-workspace reports-workspace">
        <section className="student-panel mastery-map" role="region" aria-label="掌握度地图">
          <div className="student-panel-heading">
            <div>
              <p className="section-kicker">掌握度</p>
              <h2>知识掌握度</h2>
            </div>
            <ChartLineUp size={24} weight="duotone" aria-hidden="true" />
          </div>
          <div className="mastery-list">
            {masteryRows.map((row) => (
              <article key={row.title}>
                <div>
                  <strong>{row.title}</strong>
                  <span>{row.value}</span>
                </div>
                <div className="mastery-meter" aria-label={`${row.title} ${row.progress}%`}>
                  <span style={{ width: `${row.progress}%` }} />
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="student-panel learning-report-panel" role="region" aria-label="学习报告">
          <div className="report-brief">
            <FileText size={24} weight="duotone" aria-hidden="true" />
            <div>
              <strong>本周掌握度正在生成</strong>
              <p>报告页会承接 ECharts 掌握度图、错因总结、引用证据和 Markdown 学习档案导出。</p>
            </div>
          </div>
          <ul className="report-evidence-list">
            <li>
              <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
              <span>引用覆盖：AI 导论内置讲义、期末复习题样例</span>
            </li>
            <li>
              <Graph size={17} weight="duotone" aria-hidden="true" />
              <span>画像变化：反向传播从待学习变为薄弱点</span>
            </li>
          </ul>
        </section>

        <aside className="student-panel export-panel" role="region" aria-label="导出学习档案">
          <div>
            <p className="section-kicker">学习档案</p>
            <h2>给答辩和复盘留证据</h2>
            <p>导出内容默认只包含学习过程、引用来源和掌握度，不包含真实密钥或隐私原文。</p>
          </div>
          <button className="soft-button" type="button" onClick={() => showNotice("已准备导出演示档案，真实导出会走服务端脱敏流程。", "success")}>
            <FileArrowUp size={17} aria-hidden="true" />
            <span>导出档案</span>
          </button>
          <ActionNotice notice={notice} />
        </aside>
      </div>
    </PageFrame>
  );
}
