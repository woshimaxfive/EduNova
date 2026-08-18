import { describe, expect, it } from "vitest";

import {
  CHAT_MODEL_PROVIDER_PRESETS,
  EMBEDDING_MODEL_PROVIDER_PRESETS,
  RERANK_MODEL_PROVIDER_PRESETS,
  getChatProviderPreset,
  getEmbeddingProviderPreset,
  getRerankProviderPreset,
  inferChatProviderPresetId,
  inferEmbeddingProviderPresetId,
  inferRerankProviderPresetId
} from "./modelProviders";

describe("model provider presets", () => {
  it("keeps chat, embedding, and rerank providers as separate capability lists", () => {
    const chatIds = CHAT_MODEL_PROVIDER_PRESETS.map((preset) => preset.id);
    const embeddingIds = EMBEDDING_MODEL_PROVIDER_PRESETS.map((preset) => preset.id);
    const rerankIds = RERANK_MODEL_PROVIDER_PRESETS.map((preset) => preset.id);

    expect(chatIds).toEqual(expect.arrayContaining(["spark", "deepseek", "qwen", "kimi", "zhipu"]));
    expect(embeddingIds).toEqual(["none", "xfyun-embedding", "qwen", "siliconflow-embedding", "custom"]);
    expect(rerankIds).toEqual(["none", "siliconflow-rerank", "bailian-rerank", "custom"]);
    expect(embeddingIds).not.toEqual(chatIds);
    expect(rerankIds).not.toEqual(embeddingIds);
  });

  it("uses X2-Flash and provider-specific dynamic retrieval presets", () => {
    expect(getChatProviderPreset("spark")).toMatchObject({
      baseUrl: "https://spark-api-open.xf-yun.com/agent/v1/",
      chatModel: "spark-x"
    });
    expect(getChatProviderPreset("deepseek").chatModel).toBe("deepseek-v4-pro");
    expect(getChatProviderPreset("qwen").chatModel).toBe("qwen3.7-plus");
    expect(getChatProviderPreset("zhipu").chatModel).toBe("glm-5");
    expect(getEmbeddingProviderPreset("qwen")).toMatchObject({
      baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      embeddingModel: "text-embedding-v4",
      dimension: 2048
    });
    expect(getEmbeddingProviderPreset("xfyun-embedding")).toMatchObject({
      provider: "xfyun_embedding",
      embeddingModel: "llm-embedding",
      dimension: 2560
    });
    expect(getEmbeddingProviderPreset("siliconflow-embedding")).toMatchObject({
      embeddingModel: "BAAI/bge-m3",
      dimension: 1024
    });
    expect(getRerankProviderPreset("siliconflow-rerank").rerankModel).toBe("BAAI/bge-reranker-v2-m3");
    expect(getRerankProviderPreset("bailian-rerank")).toMatchObject({
      baseUrl: "https://dashscope.aliyuncs.com/compatible-api/v1",
      rerankModel: "qwen3-rerank",
      provider: "bailian_rerank"
    });
  });

  it("infers legacy saved connections without mixing unsupported provider capabilities", () => {
    expect(inferChatProviderPresetId("https://api.deepseek.com", "deepseek")).toBe("deepseek");
    expect(inferEmbeddingProviderPresetId(
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "qwen"
    )).toBe("qwen");
    expect(inferEmbeddingProviderPresetId("https://api.deepseek.com", "deepseek")).toBe("custom");
    expect(inferEmbeddingProviderPresetId(null, null)).toBe("none");
    expect(inferRerankProviderPresetId("https://api.siliconflow.cn/v1", "siliconflow-rerank")).toBe(
      "siliconflow-rerank"
    );
    expect(inferRerankProviderPresetId("https://dashscope.aliyuncs.com/compatible-api/v1")).toBe("bailian-rerank");
    expect(inferRerankProviderPresetId(null, null)).toBe("none");
  });
});
