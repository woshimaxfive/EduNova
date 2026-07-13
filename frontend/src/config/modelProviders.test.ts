import { describe, expect, it } from "vitest";

import {
  CHAT_MODEL_PROVIDER_PRESETS,
  EMBEDDING_MODEL_PROVIDER_PRESETS,
  getChatProviderPreset,
  getEmbeddingProviderPreset,
  inferChatProviderPresetId,
  inferEmbeddingProviderPresetId
} from "./modelProviders";

describe("model provider presets", () => {
  it("keeps chat and embedding providers as separate capability lists", () => {
    const chatIds = CHAT_MODEL_PROVIDER_PRESETS.map((preset) => preset.id);
    const embeddingIds = EMBEDDING_MODEL_PROVIDER_PRESETS.map((preset) => preset.id);

    expect(chatIds).toEqual(expect.arrayContaining(["spark", "deepseek", "qwen", "kimi", "zhipu"]));
    expect(embeddingIds).toEqual(["none", "qwen", "siliconflow-embedding", "custom"]);
    expect(embeddingIds).not.toEqual(chatIds);
    expect(embeddingIds).not.toEqual(expect.arrayContaining(["spark", "deepseek", "kimi"]));
  });

  it("uses current domestic presets that can satisfy the 1536-dimension store", () => {
    expect(getChatProviderPreset("spark").chatModel).toBe("4.0Ultra");
    expect(getChatProviderPreset("deepseek").chatModel).toBe("deepseek-v4-pro");
    expect(getChatProviderPreset("qwen").chatModel).toBe("qwen3.7-plus");
    expect(getChatProviderPreset("zhipu").chatModel).toBe("glm-5");
    expect(getEmbeddingProviderPreset("qwen")).toMatchObject({
      baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      embeddingModel: "text-embedding-v4"
    });
    expect(getEmbeddingProviderPreset("siliconflow-embedding").embeddingModel).toBe(
      "Qwen/Qwen3-Embedding-8B"
    );
  });

  it("infers legacy saved connections without mixing unsupported provider capabilities", () => {
    expect(inferChatProviderPresetId("https://api.deepseek.com", "deepseek")).toBe("deepseek");
    expect(inferEmbeddingProviderPresetId(
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "qwen"
    )).toBe("qwen");
    expect(inferEmbeddingProviderPresetId("https://api.deepseek.com", "deepseek")).toBe("custom");
    expect(inferEmbeddingProviderPresetId(null, null)).toBe("none");
  });
});
