import { ChartLineUp, FileArrowUp, FileText, Graph, ShieldCheck } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

const masteryRows = [
  { title: "课程掌握度", value: "待生成", progress: 0 },
  { title: "练习表现", value: "待生成", progress: 0 },
  { title: "复习稳定性", value: "待生成", progress: 0 }
];

export function ReportsPage() {
  const [isReportReady, setIsReportReady] = useState(false);
  const [exportCount, setExportCount] = useState(0);
  const { notice, showNotice } = useActionNotice();

  function exportReport() {
    setIsReportReady(true);
    setExportCount((current) => current + 1);
    showNotice("学习档案已准备好。", "success");
  }

  return (
    <PageFrame title="学习报告">
      <div className="student-workspace reports-workspace">
        <section className="student-panel mastery-map" role="region" aria-label="掌握度地图">
          <div className="student-panel-heading">
            <div>
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
              <strong>{isReportReady ? "本周学习档案已生成" : "本周掌握度正在生成"}</strong>
              <p>{isReportReady ? "已整理画像、错因、引用和复习建议。" : "包含掌握度、错因、引用和导出。"}</p>
            </div>
          </div>
          <ul className="report-evidence-list">
            <li>
              <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
              <span>{isReportReady ? "本地预览：已整理本次导出请求" : "暂无真实报告依据"}</span>
            </li>
            <li>
              <Graph size={17} weight="duotone" aria-hidden="true" />
              <span>{isReportReady ? "本地预览：暂无画像变化记录" : "完成课程问答或练习后会形成报告线索"}</span>
            </li>
          </ul>
        </section>

        <aside className="student-panel export-panel" role="region" aria-label="导出学习档案">
          <div>
            <h2>导出档案</h2>
            <p>默认不包含密钥或隐私原文。</p>
          </div>
          {isReportReady ? <p className="export-ready-note">已生成 {exportCount} 份学习档案，可重新导出。</p> : null}
          <button className="soft-button" type="button" onClick={exportReport}>
            <FileArrowUp size={17} aria-hidden="true" />
            <span>导出档案</span>
          </button>
          <ActionNotice notice={notice} />
        </aside>
      </div>
    </PageFrame>
  );
}
