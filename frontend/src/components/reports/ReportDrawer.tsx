import { DownloadSimple, FileText, ShieldCheck, X } from "@phosphor-icons/react";

import type { ExportFormat } from "../../api/exports";
import type { AssessmentReport } from "../../api/reports";
import { AgentTraceDisclosure } from "../evidence/AgentTraceDisclosure";

export type ReportDrawerMode = "details" | "export" | null;
export type ReportDetailTab = "summary" | "evidence" | "trace";

type ReportDrawerProps = {
  mode: ReportDrawerMode;
  detailTab: ReportDetailTab;
  report: AssessmentReport | null | undefined;
  exportFormat: ExportFormat;
  isExporting: boolean;
  exportMessage: string;
  exportError: string;
  canExport: boolean;
  onClose: () => void;
  onDetailTabChange: (tab: ReportDetailTab) => void;
  onExportFormatChange: (format: ExportFormat) => void;
  onExport: () => void;
};

const formats: Array<{ value: ExportFormat; label: string; detail: string }> = [
  { value: "markdown", label: "Markdown", detail: "轻量文本档案" },
  { value: "pdf", label: "PDF", detail: "便于阅读与打印" },
  { value: "docx", label: "DOCX", detail: "便于继续编辑" }
];

export function ReportDrawer({
  mode,
  detailTab,
  report,
  exportFormat,
  isExporting,
  exportMessage,
  exportError,
  canExport,
  onClose,
  onDetailTabChange,
  onExportFormatChange,
  onExport
}: ReportDrawerProps) {
  if (!mode) return null;
  const ready = report?.status === "ready";
  const body = report?.report;
  const title = mode === "details" ? "报告详情" : "导出学习档案";

  return (
    <div className="report-drawer-layer" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside className="report-drawer" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <div><span>学习报告</span><h2>{title}</h2></div>
          <button type="button" aria-label={`关闭${title}`} onClick={onClose}><X size={19} weight="bold" aria-hidden="true" /></button>
        </header>

        {mode === "details" ? (
          <>
            <div className="report-drawer-tabs" role="tablist" aria-label="报告详情分类">
              {([
                ["summary", "总结与建议"],
                ["evidence", "证据与审核"],
                ["trace", "协作轨迹"]
              ] as const).map(([value, label]) => (
                <button key={value} type="button" role="tab" aria-selected={detailTab === value} onClick={() => onDetailTabChange(value)}>{label}</button>
              ))}
            </div>
            <div className="report-drawer-content">
              {!ready ? (
                <div className="report-drawer-empty"><FileText size={30} weight="duotone" /><h3>还没有正式报告</h3><p>完成练习并主动生成报告后，这里会展示报告快照。</p></div>
              ) : detailTab === "summary" ? (
                <div className="report-detail-sections">
                  <section><span>生成时学习结论</span><p>{body?.summary}</p></section>
                  <section><span>下一步建议</span><ol>{(body?.next_step_suggestions ?? []).map((item) => <li key={item}>{item}</li>)}</ol></section>
                  <section><span>画像变化</span>{body?.profile_changes.length ? <ul>{body.profile_changes.map((item) => <li key={item}>{item}</li>)}</ul> : <p>本次没有写入新的长期画像变化。</p>}</section>
                </div>
              ) : detailTab === "evidence" ? (
                <div className="report-detail-sections">
                  <section>
                    <span>证据摘要</span>
                    <div className="report-evidence-facts">
                      <strong>{body?.evidence_summary?.practice_count ?? 0}<small>次练习</small></strong>
                      <strong>{body?.evidence_summary?.answer_count ?? 0}<small>条作答</small></strong>
                      <strong>{body?.evidence_summary?.weakness_count ?? 0}<small>个弱点</small></strong>
                      <strong>{body?.evidence_summary?.resource_count ?? 0}<small>个资源</small></strong>
                    </div>
                  </section>
                  <section><span>薄弱点证据</span>{body?.weakness_list.length ? <ul>{body.weakness_list.map((item) => <li key={`${item.knowledge_point_id}-${item.title}`}><ShieldCheck size={16} />{item.title}</li>)}</ul> : <p>本次快照没有记录薄弱点。</p>}</section>
                  <section><span>审核结果</span><p>{body?.review_result?.safety_summary || "当前报告没有附加审核摘要。"}</p><small>状态 {body?.review_result?.review_status || "未提供"} · 置信度 {Math.round((body?.review_result?.confidence ?? 0) * 100)}%</small></section>
                </div>
              ) : (
                <div className="report-trace-panel">
                  <p>展示 ReportGraph 使用练习、掌握度、弱点和路径证据生成报告的安全执行轨迹。</p>
                  <AgentTraceDisclosure traceId={report?.agent_trace_id} label="查看 ReportGraph" />
                  {!report?.agent_trace_id ? <p className="empty-inline-note">当前报告没有可查询的协作轨迹。</p> : null}
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="report-drawer-content report-export-content">
              <div className="report-export-intro"><DownloadSimple size={28} weight="duotone" /><div><h3>导出当前学习档案</h3><p>{ready ? "档案包含最新报告快照与已有学习数据。" : "当前没有正式报告，仍可导出课程、画像、路径等已有学习数据。"}</p></div></div>
              <fieldset className="report-format-options">
                <legend>选择格式</legend>
                {formats.map((format) => (
                  <button key={format.value} type="button" aria-pressed={exportFormat === format.value} onClick={() => onExportFormatChange(format.value)}>
                    <FileText size={19} weight="duotone" /><span><strong>{format.label}</strong><small>{format.detail}</small></span>
                  </button>
                ))}
              </fieldset>
              {isExporting ? <div className="report-export-progress" role="status"><span /><p>正在生成并准备下载，请保持页面打开。</p></div> : null}
              {exportMessage ? <p className="inline-feedback inline-feedback-success">{exportMessage}</p> : null}
              {exportError ? <p className="form-error">{exportError}</p> : null}
            </div>
            <footer><span>{formats.find((format) => format.value === exportFormat)?.detail}</span><button className="primary" type="button" disabled={!canExport || isExporting} onClick={onExport}><DownloadSimple size={17} weight="bold" />{isExporting ? "正在导出" : `导出 ${formats.find((format) => format.value === exportFormat)?.label}`}</button></footer>
          </>
        )}
      </aside>
    </div>
  );
}
