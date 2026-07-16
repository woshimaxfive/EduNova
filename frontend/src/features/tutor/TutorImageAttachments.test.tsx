import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TutorImagePicker } from "./TutorImageAttachments";
import { hasUsableVisionModel, type useTutorImageDraft } from "./useTutorImageDraft";

describe("TutorImagePicker", () => {
  it("没有个人视觉默认时接受服务器图片理解兜底", () => {
    expect(hasUsableVisionModel({
      configs: [],
      default_config_id: null,
      default_chat_config_id: null,
      default_embedding_config_id: null,
      default_rerank_config_id: null,
      default_vision_config_id: null,
      system_summary: {
        source: "system",
        provider: "openai_compatible",
        base_url: null,
        api_key_masked: null,
        has_api_key: false,
        chat_model: null,
        embedding_provider: null,
        embedding_base_url: null,
        embedding_api_key_masked: null,
        embedding_app_id_masked: null,
        embedding_model: null,
        rerank_provider: null,
        rerank_base_url: null,
        rerank_model: null,
        rerank_workspace_id: null,
        has_embedding_api_key: false,
        has_embedding_app_id: false,
        has_embedding_api_secret: false,
        has_rerank_api_key: false,
        rerank_api_key_masked: null,
        can_use_model: false,
        can_use_embedding_model: false,
        can_use_rerank_model: false,
        vision_provider: "xfyun_vision",
        vision_base_url: "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
        vision_model: "imagev3",
        can_use_vision_model: true
      }
    })).toBe(true);
  });

  it("在新标签打开视觉模型设置，避免卸载当前图片草稿", () => {
    const draft = {
      images: [],
      addFiles: vi.fn(),
      removeImage: vi.fn(),
      clearAfterSend: vi.fn(),
      discardAll: vi.fn(),
      attachmentIds: [],
      uploading: false,
      hasFailed: false,
      visionReady: false
    } as unknown as ReturnType<typeof useTutorImageDraft>;

    render(<MemoryRouter><TutorImagePicker draft={draft} /></MemoryRouter>);

    const link = screen.getByRole("link", { name: "配置图片理解模型" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("用一个入口上传资料并选择资料库图片", async () => {
    const user = userEvent.setup();
    const addMaterial = vi.fn();
    const draft = {
      images: [], addFiles: vi.fn(), addMaterial, removeImage: vi.fn(), clearAfterSend: vi.fn(), discardAll: vi.fn(),
      libraryImages: [{ id: "41", title: "课堂截图.png", size: "18 KB", category: "image" }],
      attachmentIds: [], uploading: false, hasFailed: false, visionReady: true
    } as unknown as ReturnType<typeof useTutorImageDraft>;
    render(<MemoryRouter><TutorImagePicker draft={draft} /></MemoryRouter>);

    expect(screen.getAllByRole("button", { name: "添加资料" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "添加资料" }));
    expect(screen.getByRole("button", { name: "上传文件或图片" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /课堂截图.png/ }));
    expect(addMaterial).toHaveBeenCalledWith(expect.objectContaining({ id: "41" }));
  });
});
