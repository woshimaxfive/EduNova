import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TutorImagePicker } from "./TutorImageAttachments";
import type { useTutorImageDraft } from "./useTutorImageDraft";

describe("TutorImagePicker", () => {
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
});
