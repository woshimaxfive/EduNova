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
};

export const CHAT_MODEL_PROVIDER_PRESETS: ChatModelProviderPreset[] = [
  {
    id: "spark",
    name: "讯飞星火 Spark",
    description: "赛题出题企业相关 Provider，按星火 HTTP OpenAI-compatible 接口接入。",
    baseUrl: "https://spark-api-open.xf-yun.com/v1",
    chatModel: "4.0Ultra",
    apiKeyLabel: "API Key / APIPassword",
    apiKeyPlaceholder: "填入讯飞控制台对应模型的 APIPassword",
    modelsHint: "推荐 4.0Ultra；也可使用 generalv3、pro-128k 或 lite。"
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
    allowEmptyApiKey: true
  },
  {
    id: "qwen",
    name: "阿里云百炼 · 文本向量",
    description: "百炼 OpenAI-compatible 向量接口，可直接输出项目使用的 1536 维向量。",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    embeddingModel: "text-embedding-v4",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入百炼 API Key",
    modelsHint: "推荐 text-embedding-v4；EduNova 请求 1536 维输出。"
  },
  {
    id: "siliconflow-embedding",
    name: "硅基流动 · Qwen3 Embedding",
    description: "硅基流动 OpenAI-compatible 向量接口，Qwen3 Embedding 支持 1536 维输出。",
    baseUrl: "https://api.siliconflow.cn/v1",
    embeddingModel: "Qwen/Qwen3-Embedding-8B",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 SiliconFlow API Key",
    modelsHint: "推荐 Qwen/Qwen3-Embedding-8B；也可按账号可用模型调整。"
  },
  {
    id: "custom",
    name: "自定义 1536 维兼容服务",
    description: "适合私有网关或其它支持 OpenAI /embeddings 且能返回 1536 维向量的服务。",
    baseUrl: "",
    embeddingModel: "",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入向量服务 API Key"
  }
];

export function getChatProviderPreset(presetId: string | null | undefined) {
  return CHAT_MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId) ?? CHAT_MODEL_PROVIDER_PRESETS[0];
}

export function getEmbeddingProviderPreset(presetId: string | null | undefined) {
  return EMBEDDING_MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId)
    ?? EMBEDDING_MODEL_PROVIDER_PRESETS[0];
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
