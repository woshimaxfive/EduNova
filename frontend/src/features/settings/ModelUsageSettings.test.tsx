import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { getModelUsage, type ModelUsageReport } from "../../api/modelUsage";
import { ModelUsageSettings } from "./ModelUsageSettings";
import { tokenCount } from "./usageFormatting";
import { SettingsNavigation } from "./SettingsNavigation";

vi.mock("../../api/modelUsage", () => ({ getModelUsage: vi.fn() }));
afterEach(() => vi.resetAllMocks());

const empty: ModelUsageReport = {
  days: 7, since: "2026-09-18T00:00:00Z", until: "2026-09-25T00:00:00Z", retention_days: 30,
  limit: 1000, truncated: false, call_count: 0, failed_count: 0, retry_count: 0,
  observed_attempt_count: 0, legacy_call_count: 0, totals: {}, cost_subtotals: {}, priced_call_count: 0, recent: []
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ModelUsageSettings /></QueryClientProvider>);
}

it("distinguishes unknown, partial and actual zero", () => {
  expect(tokenCount(null)).toBe("未知");
  expect(tokenCount(null, 0)).toBe("已知 0 · 部分未知");
  expect(tokenCount(0)).toBe("0");
});

it("shows empty state and changes the requested time window", async () => {
  vi.mocked(getModelUsage).mockResolvedValue(empty);
  mount();
  expect(await screen.findByText(/这个时间段暂无模型调用记录/)).toBeInTheDocument();
  expect(screen.getByText(/只统计当前账号的主模型调用/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "30" } });
  await waitFor(() => expect(getModelUsage).toHaveBeenCalledWith(30));
});

it("shows bounded partial totals and does not invent a cost or hit ratio", async () => {
  vi.mocked(getModelUsage).mockResolvedValue({ ...empty, truncated: true, call_count: 1000,
    totals: { input_tokens: null, known_input_tokens: 100, output_tokens: 0, cache_hit_ratio: null },
    recent: [{ id: "1", started_at: empty.until, model_name: "fixture", purpose: "chat", status: "failed", retry_count: 1, usage: {} }]
  });
  mount();
  expect(await screen.findByText("已知 100 · 部分未知")).toBeInTheDocument();
  expect(screen.getByText(/以下汇总仅覆盖最近/)).toBeInTheDocument();
  expect(screen.getByText(/可估算 0 \/ 1000/)).toBeInTheDocument();
  expect(screen.getAllByText("未知").length).toBeGreaterThan(1);
  expect(screen.getByText("失败 · 重试 1 次")).toBeInTheDocument();
});

it("allows retry after a failed request", async () => {
  vi.mocked(getModelUsage).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(empty);
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("用量读取失败");
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  expect(await screen.findByText(/这个时间段暂无模型调用记录/)).toBeInTheDocument();
});

it("exposes the settings navigation entry", () => {
  const onSelect = vi.fn();
  render(<SettingsNavigation activeSection="usage" onSelect={onSelect} />);
  const button = screen.getByRole("button", { name: /模型用量/ });
  expect(button).toHaveAttribute("aria-current", "page");
  fireEvent.click(button);
  expect(onSelect).toHaveBeenCalledWith("usage");
});
