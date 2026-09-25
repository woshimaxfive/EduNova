import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import "../../styles/settings-usage.css";

import { getModelUsage } from "../../api/modelUsage";
import { useAuthStore } from "../auth/authStore";
import { tokenCount } from "./usageFormatting";

function ratio(value: number | null | undefined) {
  return value == null ? "未知" : `${(value * 100).toFixed(1)}%`;
}

const STATUS: Record<string, string> = { completed: "完成", failed: "失败", cancelled: "已取消" };

export function ModelUsageSettings() {
  const [days, setDays] = useState(7);
  const userId = useAuthStore((state) => state.user?.id);
  const query = useQuery({
    queryKey: ["settings", "model-usage", userId, days],
    queryFn: () => getModelUsage(days),
    staleTime: 30_000
  });
  const report = query.data;

  return (
    <section className="settings-panel settings-usage" aria-label="模型用量">
      <header className="settings-panel-heading">
        <div><h2>模型用量</h2><p>只统计当前账号的主模型调用（含对话、生成和图片理解），不包含向量、重排等辅助服务；不是供应商账单。</p></div>
      </header>
      <div className="settings-usage-controls">
        <label>统计时间 <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
          <option value={1}>最近 24 小时</option><option value={7}>最近 7 天</option><option value={30}>最近 30 天</option>
        </select></label>
        <button className="secondary-action" type="button" disabled={query.isFetching} onClick={() => void query.refetch()}>
          {query.isFetching ? "加载中…" : "刷新"}
        </button>
      </div>
      {query.isPending ? <p role="status">正在读取模型用量…</p> : null}
      {query.isError ? <p role="alert">用量读取失败，请点击刷新重试。{report ? "下方保留上次读取的结果。" : ""}</p> : null}
      {report ? <>
        <p className="settings-usage-note">截至 {new Date(report.until).toLocaleString()} · 日志保留 {report.retention_days} 天。旧记录或供应商未返回的字段显示为未知。</p>
        {report.truncated ? <p role="status">当前时间段超过 {report.limit} 条记录；以下汇总仅覆盖最近 {report.limit} 条调用。</p> : null}
        {!report.call_count ? <p role="status">这个时间段暂无模型调用记录。使用 AI 回答或生成功能后，刷新这里查看。</p> : <>
          <dl className="settings-usage-metrics">
            <div><dt>调用记录</dt><dd>{report.call_count.toLocaleString()}</dd><small>{report.failed_count} 次失败 · {report.retry_count} 次重试 · {report.observed_attempt_count} 次已观测尝试</small></div>
            <div><dt>输入 token</dt><dd>{tokenCount(report.totals.input_tokens, report.totals.known_input_tokens)}</dd><small>包含已上报的缓存输入</small></div>
            <div><dt>输出 token</dt><dd>{tokenCount(report.totals.output_tokens, report.totals.known_output_tokens)}</dd><small>不重复叠加推理 token</small></div>
            <div><dt>缓存命中率</dt><dd>{ratio(report.totals.cache_hit_ratio)}</dd><small>缓存读取 token / 输入 token；不是请求成功率</small></div>
          </dl>
          <div className="settings-usage-cost">
            <h3>已知估算费用</h3>
            <strong>{Object.entries(report.cost_subtotals ?? {}).map(([currency, value]) => `${currency} ${value}`).join(" / ") || "未知"}</strong>
            <p>可估算 {report.priced_call_count} / {report.call_count} 条调用。只使用调用时配置的价格；不同币种分别汇总，缺少价格或用量不等于免费，实际费用以供应商账单为准。</p>
          </div>
          <h3>最近调用</h3>
          <div className="settings-usage-table" role="region" aria-label="最近模型调用" tabIndex={0}>
            <table><thead><tr><th>时间 / 模型</th><th>用途 / 状态</th><th>输入 / 输出 token</th><th>缓存命中</th><th>估算费用</th></tr></thead>
              <tbody>{report.recent.map((call) => <tr key={call.id}>
                <td>{new Date(call.started_at).toLocaleString()}<small>{call.model_name}</small></td>
                <td>{call.purpose}<small>{STATUS[call.status] ?? call.status}{call.retry_count ? ` · 重试 ${call.retry_count} 次` : ""}</small></td>
                <td>{tokenCount(call.usage.input_tokens, call.usage.known_input_tokens)} / {tokenCount(call.usage.output_tokens, call.usage.known_output_tokens)}</td>
                <td>{ratio(call.usage.cache_hit_ratio)}</td>
                <td>{call.estimated_cost != null ? `${call.currency} ${call.estimated_cost}` : "未知"}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <p className="settings-usage-note">展示最近 {report.recent.length} 条；汇总包含失败和重试已上报的用量。{report.legacy_call_count ? `其中 ${report.legacy_call_count} 条历史调用没有用量记录。` : ""}</p>
        </>}
      </> : null}
    </section>
  );
}
