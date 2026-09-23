import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getModelSettings, testModelSettings } from "../../api/settings";
import { PersonalAnswerModelSettings } from "./PersonalAnswerModelSettings";

vi.mock("../../api/settings", () => ({
  getModelSettings: vi.fn(), saveModelSettings: vi.fn(), testModelSettings: vi.fn()
}));

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><PersonalAnswerModelSettings /></QueryClientProvider>);
}

describe("personal main model capabilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getModelSettings).mockResolvedValue({
      data: {
        source: "user", provider: "openai_compatible", base_url: "https://personal.example/v1",
        chat_model: "my-model", embedding_model: null, has_api_key: true, api_key_masked: "sk-***",
        can_use_model: true, can_use_embedding_model: false, can_use_vision_model: false, vision_status: "unverified"
      }
    } as Awaited<ReturnType<typeof getModelSettings>>);
  });

  it("offers an explicit synthetic-image probe without assuming image support", async () => {
    mount();
    expect(await screen.findByText(/待验证主模型图片能力/)).toBeInTheDocument();
    expect(screen.getByText(/可能产生少量模型费用/)).toBeInTheDocument();
    expect(testModelSettings).not.toHaveBeenCalled();
    vi.mocked(testModelSettings).mockResolvedValue({ data: {
      ok: false, operation: "vision", model: "my-model", message: "请求超时，可重试", retryable: true,
      source: "user", chat_model: "my-model", tested_at: "2026-09-23T00:00:00Z"
    } } as Awaited<ReturnType<typeof testModelSettings>>);
    fireEvent.click(screen.getByRole("button", { name: "验证图片理解服务连接" }));
    await waitFor(() => expect(testModelSettings).toHaveBeenCalledWith("vision"));
    expect(await screen.findByText("请求超时，可重试")).toBeInTheDocument();
  });

  it("requires saving edited connection fields before testing", async () => {
    mount();
    await screen.findByText(/待验证主模型图片能力/);
    fireEvent.change(screen.getByRole("textbox", { name: "回答模型" }), { target: { value: "changed-model" } });
    expect(screen.getByRole("button", { name: "验证图片理解服务连接" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "验证回答服务连接" })).toBeDisabled();
    expect(testModelSettings).not.toHaveBeenCalled();
  });
});
