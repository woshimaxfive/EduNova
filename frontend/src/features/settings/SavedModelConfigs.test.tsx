import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { createModelConfig, listModelConfigs, setDefaultModelConfig } from "../../api/settings";
import { SavedModelConfigs } from "./SavedModelConfigs";
import { suggestedModelBaseUrl } from "./modelAddress";

vi.mock("../../api/settings", () => ({ listModelConfigs: vi.fn(), createModelConfig: vi.fn(), setDefaultModelConfig: vi.fn(), fetchModelCatalog: vi.fn() }));
const onSwitch = vi.fn();
function mount(disabled = false) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><SavedModelConfigs disabled={disabled} onSwitch={onSwitch} /></QueryClientProvider>);
  fireEvent.click(screen.getByText("管理多套配置（可选）"));
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listModelConfigs).mockResolvedValue({ data: { configs: [
    { id: 1, display_name: "日常", chat_model: "fast", is_default: true, base_url: "https://a.example/v1" },
    { id: 2, display_name: "备用", chat_model: "smart", is_default: false, base_url: "https://b.example/v1" }
  ] } } as Awaited<ReturnType<typeof listModelConfigs>>);
});
it("switches only after explicit confirmation", async () => {
  vi.mocked(setDefaultModelConfig).mockResolvedValue({} as Awaited<ReturnType<typeof setDefaultModelConfig>>);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "启用 备用" }));
  expect(setDefaultModelConfig).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "确认切换主模型" }));
  await waitFor(() => expect(setDefaultModelConfig).toHaveBeenCalledWith(2, expect.anything()));
  await waitFor(() => expect(onSwitch).toHaveBeenCalled());
});
it("saves a new configuration without enabling or copying a key", async () => {
  vi.mocked(createModelConfig).mockResolvedValue({} as Awaited<ReturnType<typeof createModelConfig>>);
  mount();
  await screen.findByText("备用");
  fireEvent.click(screen.getByRole("button", { name: "添加模型配置" }));
  expect(screen.getByLabelText("新配置 API Key")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("配置名称"), { target: { value: "研究" } });
  fireEvent.change(screen.getByLabelText("新配置 Base URL"), { target: { value: "https://new.example/v1" } });
  fireEvent.change(screen.getByLabelText("新配置 API Key"), { target: { value: "synthetic-key" } });
  fireEvent.change(screen.getByLabelText("新配置模型名称"), { target: { value: "research" } });
  fireEvent.click(screen.getByRole("button", { name: "保存新配置" }));
  await waitFor(() => expect(createModelConfig).toHaveBeenCalledWith(expect.objectContaining({ make_default: false, api_key: "synthetic-key", chat_model: "research" })));
  expect(setDefaultModelConfig).not.toHaveBeenCalled();
});
it("prevents switching while current editor is dirty or testing", async () => {
  mount(true);
  expect(await screen.findByRole("button", { name: "启用 备用" })).toBeDisabled();
});
it("suggests exact endpoint suffix removal, preserving custom prefixes", () => {
  expect(suggestedModelBaseUrl("https://example.org/compatible-mode/v1/chat/completions")).toBe("https://example.org/compatible-mode/v1");
  expect(suggestedModelBaseUrl("https://example.org/v1/responses")).toBe("https://example.org/v1");
  expect(suggestedModelBaseUrl("https://example.org/custom/path")).toBeNull();
  expect(suggestedModelBaseUrl("https://example.org/v1?key=secret")).toBeNull();
});
