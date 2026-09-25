import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as memory from "../../api/memory";
import * as settings from "../../api/settings";
import { MemorySettings } from "./MemorySettings";

vi.mock("../../api/memory", () => ({ listMemories: vi.fn(), createMemory: vi.fn(), correctMemory: vi.fn(), deleteMemory: vi.fn(),
  clearMemoryIndexes: vi.fn(), rebuildMemoryIndexes: vi.fn(), exportMemories: vi.fn() }));
vi.mock("../../api/settings", () => ({ getPrivacySettings: vi.fn(), updatePrivacySettings: vi.fn(), clearConversationMemory: vi.fn() }));
afterEach(() => vi.resetAllMocks());
const item: memory.MemoryItem = { id: "11", layer: "episode", category: "episode", content: "学习队列", topic: "队列", source: "历史会话摘要",
  session_id: "12", user_message_id: "13", assistant_message_id: "14", created_at: "2026-09-25T00:00:00Z", updated_at: "2026-09-25T00:00:00Z", revision: 2, indexed: true };
function mount() {
  vi.mocked(settings.getPrivacySettings).mockResolvedValue({ data: { conversation_memory_enabled: true, indexed_memory_count: 1, episode_count: 1, confirmed_fact_count: 0 }, trace_id: "test" });
  vi.mocked(memory.listMemories).mockResolvedValue({ items: [item], total: 1, page: 1, page_size: 20 });
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemorySettings /></QueryClientProvider>);
}
it("requires explicit confirmation before saving a long-term fact", async () => {
  mount();
  await screen.findByText("学习队列");
  fireEvent.change(screen.getByLabelText("长期学习信息"), { target: { value: "先给例子" } });
  expect(screen.getByRole("button", { name: "保存长期信息" })).toBeDisabled();
  fireEvent.click(screen.getByLabelText("我确认这条信息，并希望在后续对话中使用"));
  fireEvent.click(screen.getByRole("button", { name: "保存长期信息" }));
  await waitFor(() => expect(memory.createMemory).toHaveBeenCalledWith({ category: "goal", content: "先给例子", confirmed: true }));
});
it("pauses without clearing stored memory and shows source metadata", async () => {
  mount();
  expect(await screen.findByText(/会话 12 · 消息 13 \/ 14/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("跨会话记忆"));
  await waitFor(() => expect(settings.updatePrivacySettings).toHaveBeenCalledWith(false));
  expect(settings.clearConversationMemory).not.toHaveBeenCalled();
});
it("cancels deletion and requires confirmation before permanent removal", async () => {
  mount(); await screen.findByText("学习队列");
  fireEvent.click(screen.getByRole("button", { name: "永久删除" }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "取消" }));
  expect(memory.deleteMemory).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "永久删除" }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "确认操作" }));
  await waitFor(() => expect(memory.deleteMemory).toHaveBeenCalledWith(item));
});
it("preserves a correction draft on failure and sends the original revision", async () => {
  vi.mocked(memory.correctMemory).mockRejectedValue(new Error("conflict"));
  mount(); await screen.findByText("学习队列");
  fireEvent.click(screen.getByRole("button", { name: "纠正" }));
  fireEvent.change(screen.getByLabelText("纠正内容"), { target: { value: "双端队列" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存纠正" }));
  await screen.findByRole("alert");
  expect(memory.correctMemory).toHaveBeenCalledWith(item, "双端队列");
  expect(screen.getByLabelText("纠正内容")).toHaveValue("双端队列");
});

it.each([
  ["清除派生索引", memory.clearMemoryIndexes],
  ["清除全部记忆", settings.clearConversationMemory]
] as const)("requires confirmation for %s and renders outside route styles", async (label, action) => {
  mount(); await screen.findByText("学习队列");
  const panel = screen.getByRole("region", { name: "记忆管理" });
  fireEvent.click(screen.getByRole("button", { name: label }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog.parentElement).toBe(document.body);
  expect(panel).not.toContainElement(dialog);
  expect(action).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole("button", { name: "取消" }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(action).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: label }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "确认操作" }));
  await waitFor(() => expect(action).toHaveBeenCalledOnce());
});
