type ModelProviderPresetBase = {
  id: string;
  name: string;
  description: string;
  baseUrl: string;
  apiKeyLabel: string;
  apiKeyPlaceholder: string;
  modelsHint?: string;
  allowEmptyApiKey?: boolean;
};

export type ChatModelProviderPreset = ModelProviderPresetBase & {
  chatModel: string;
};

export type EmbeddingModelProviderPreset = ModelProviderPresetBase & {
  embeddingModel: string;
  provider: "openai_compatible" | "xfyun_embedding";
  dimension: number | null;
  requiresXfyunCredentials?: boolean;
};

export type RerankModelProviderPreset = ModelProviderPresetBase & {
  rerankModel: string;
  provider: "siliconflow_rerank" | "bailian_rerank" | "openai_compatible";
  requiresWorkspaceId?: boolean;
};

export const CHAT_MODEL_PROVIDER_PRESETS: ChatModelProviderPreset[] = [
  {
    id: "spark",
    name: "讯飞星火 X2-Flash",
    description: "赛题出题企业相关模型，支持标准回答与可控深度思考。联网仍由 EduNova 的来源检索负责。",
    baseUrl: "https://spark-api-open.xf-yun.com/agent/v1/",
    chatModel: "spark-x",
    apiKeyLabel: "API Key / APIPassword",
    apiKeyPlaceholder: "填入讯飞控制台对应模型的 APIPassword",
    modelsHint: "默认 Spark X2-Flash（spark-x）；额度与可用能力以讯飞控制台为准。"
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek 官方 OpenAI-compatible 接口，适合通用问答、推理与课程 RAG。",
    baseUrl: "https://api.deepseek.com",
    chatModel: "deepseek-v4-pro",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 DeepSeek API Key",
    modelsHint: "推荐 deepseek-v4-pro；追求速度可使用 deepseek-v4-flash。"
  },
  {
    id: "qwen",
    name: "阿里云百炼 · 千问",
    description: "阿里云百炼公共云 OpenAI-compatible 接口，适合中文学习问答与 Agent 任务。",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen3.7-plus",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入百炼 API Key",
    modelsHint: "推荐 qwen3.7-plus；需要更低延迟可使用 qwen3.6-flash。"
  },
  {
    id: "kimi",
    name: "Kimi",
    description: "Kimi 官方 OpenAI-compatible 接口，适合长上下文与通用学习问答。",
    baseUrl: "https://api.moonshot.cn/v1",
    chatModel: "kimi-k2.6",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 Kimi API Key",
    modelsHint: "通用学习问答推荐 kimi-k2.6；kimi-k2.7-code 更偏代码任务。"
  },
  {
    id: "zhipu",
    name: "智谱 GLM",
    description: "智谱官方通用 API，支持标准聊天、结构化输出与工具调用。",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    chatModel: "glm-5",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入智谱 API Key"
  },
  {
    id: "baidu-qianfan",
    name: "百度千帆",
    description: "百度千帆 OpenAI-compatible v2 接口。",
    baseUrl: "https://qianfan.baidubce.com/v2",
    chatModel: "ernie-5.0",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入千帆 API Key"
  },
  {
    id: "tencent-hunyuan",
    name: "腾讯混元",
    description: "腾讯混元 OpenAI-compatible 接口。",
    baseUrl: "https://api.hunyuan.cloud.tencent.com/v1",
    chatModel: "hunyuan-turbos-latest",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入腾讯混元 API Key"
  },
  {
    id: "siliconflow",
    name: "硅基流动",
    description: "硅基流动 OpenAI-compatible 接口，可按账号可用模型灵活切换。",
    baseUrl: "https://api.siliconflow.cn/v1",
    chatModel: "deepseek-ai/DeepSeek-V3.2",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 SiliconFlow API Key"
  },
  {
    id: "ollama",
    name: "本地 Ollama",
    description: "本机 Ollama OpenAI-compatible 接口，开发环境可留空 Key。",
    baseUrl: "http://localhost:11434/v1",
    chatModel: "qwen3:8b",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "本地 Ollama 通常可留空",
    allowEmptyApiKey: true
  },
  {
    id: "lm-studio",
    name: "本地 LM Studio",
    description: "LM Studio 本地 OpenAI-compatible 服务，模型名按本机加载模型填写。",
    baseUrl: "http://localhost:1234/v1",
    chatModel: "",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "本地 LM Studio 通常可留空",
    allowEmptyApiKey: true
  },
  {
    id: "custom",
    name: "自定义回答服务",
    description: "适合学校内网、私有网关或其它 OpenAI-compatible 回答服务。",
    baseUrl: "",
    chatModel: "",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入服务商 API Key"
  }
];

export const EMBEDDING_MODEL_PROVIDER_PRESETS: EmbeddingModelProviderPreset[] = [
  {
    id: "none",
    name: "暂不配置",
    description: "不调用外部向量服务，资料检索继续使用关键词 fallback。",
    baseUrl: "",
    embeddingModel: "",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "无需填写",
    allowEmptyApiKey: true,
    provider: "openai_compatible",
    dimension: null
  },
  {
    id: "xfyun-embedding",
    name: "讯飞星火 · LLM Embedding",
    description: "讯飞原生文本向量接口，资料使用 para、问题使用 query，输出 2560 维。",
    baseUrl: "https://emb-cn-huabei-1.xf-yun.com/",
    embeddingModel: "llm-embedding",
    provider: "xfyun_embedding",
    dimension: 2560,
    apiKeyLabel: "APIKey",
    apiKeyPlaceholder: "填入讯飞 Embedding APIKey",
    modelsHint: "还需要同一服务的 APPID 与 APISecret；额度以讯飞控制台为准。",
    requiresXfyunCredentials: true
  },
  {
    id: "qwen",
    name: "阿里云百炼 · 文本向量",
    description: "百炼 OpenAI-compatible 向量接口，text-embedding-v4 默认使用 1024 维。",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    embeddingModel: "text-embedding-v4",
    provider: "openai_compatible",
    dimension: 1024,
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入百炼 API Key",
    modelsHint: "推荐 text-embedding-v4；支持的维度以百炼当前文档与控制台为准。"
  },
  {
    id: "siliconflow-embedding",
    name: "硅基流动 · BGE-M3",
    description: "硅基流动 OpenAI-compatible 向量接口，适合中英文学习资料检索。",
    baseUrl: "https://api.siliconflow.cn/v1",
    embeddingModel: "BAAI/bge-m3",
    provider: "openai_compatible",
    dimension: 1024,
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 SiliconFlow API Key",
    modelsHint: "推荐 BAAI/bge-m3（1024 维）；免费额度以硅基流动控制台为准。"
  },
  {
    id: "custom",
    name: "自定义兼容向量服务",
    description: "适合私有网关或其它支持 OpenAI /embeddings 的文本向量服务。",
    baseUrl: "",
    embeddingModel: "",
    provider: "openai_compatible",
    dimension: null,
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入向量服务 API Key"
  }
];

export const RERANK_MODEL_PROVIDER_PRESETS: RerankModelProviderPreset[] = [
  {
    id: "none",
    name: "暂不配置",
    description: "使用关键词与向量的混合排序，不调用外部重排序服务。",
    baseUrl: "",
    rerankModel: "",
    provider: "openai_compatible",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "无需填写",
    allowEmptyApiKey: true
  },
  {
    id: "siliconflow-rerank",
    name: "硅基流动 · BGE Reranker",
    description: "对混合召回的候选片段进行二次精排，默认最多处理 20 条。",
    baseUrl: "https://api.siliconflow.cn/v1",
    rerankModel: "BAAI/bge-reranker-v2-m3",
    provider: "siliconflow_rerank",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 SiliconFlow API Key",
    modelsHint: "推荐 BAAI/bge-reranker-v2-m3；免费额度以控制台为准。"
  },
  {
    id: "bailian-rerank",
    name: "阿里云百炼 · Qwen3 Rerank",
    description: "使用百炼 Workspace 兼容接口对文本候选进行精排。",
    baseUrl: "https://{workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-api/v1",
    rerankModel: "qwen3-rerank",
    provider: "bailian_rerank",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入百炼 API Key",
    modelsHint: "需要填写 Workspace ID；额度以百炼控制台为准。",
    requiresWorkspaceId: true
  },
  {
    id: "custom",
    name: "自定义兼容重排序服务",
    description: "适合提供兼容 rerank 响应的私有服务。",
    baseUrl: "",
    rerankModel: "",
    provider: "openai_compatible",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入重排序服务 API Key"
  }
];

export function getChatProviderPreset(presetId: string | null | undefined) {
  return CHAT_MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId) ?? CHAT_MODEL_PROVIDER_PRESETS[0];
}

export function getEmbeddingProviderPreset(presetId: string | null | undefined) {
  return EMBEDDING_MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId)
    ?? EMBEDDING_MODEL_PROVIDER_PRESETS[0];
}

export function getRerankProviderPreset(presetId: string | null | undefined) {
  return RERANK_MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId)
    ?? RERANK_MODEL_PROVIDER_PRESETS[0];
}

export function inferChatProviderPresetId(baseUrl: string | null | undefined, presetId?: string | null) {
  if (presetId && CHAT_MODEL_PROVIDER_PRESETS.some((preset) => preset.id === presetId)) {
    return presetId;
  }
  if (!baseUrl) return "spark";
  return CHAT_MODEL_PROVIDER_PRESETS.find((preset) => preset.id !== "custom" && preset.baseUrl === baseUrl)?.id
    ?? "custom";
}

export function inferEmbeddingProviderPresetId(baseUrl: string | null | undefined, presetId?: string | null) {
  if (presetId && EMBEDDING_MODEL_PROVIDER_PRESETS.some((preset) => preset.id === presetId)) {
    return presetId;
  }
  if (!baseUrl) return "none";
  return EMBEDDING_MODEL_PROVIDER_PRESETS.find(
    (preset) => preset.id !== "none" && preset.id !== "custom" && preset.baseUrl === baseUrl
  )?.id ?? "custom";
}

export function inferRerankProviderPresetId(baseUrl: string | null | undefined, presetId?: string | null) {
  if (presetId && RERANK_MODEL_PROVIDER_PRESETS.some((preset) => preset.id === presetId)) {
    return presetId;
  }
  if (!baseUrl) return "none";
  return RERANK_MODEL_PROVIDER_PRESETS.find(
    (preset) => preset.id !== "none" && preset.id !== "custom" && preset.baseUrl === baseUrl
  )?.id ?? "custom";
}
