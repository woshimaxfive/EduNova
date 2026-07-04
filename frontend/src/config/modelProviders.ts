export type ModelProviderPreset = {
  id: string;
  name: string;
  description: string;
  baseUrl: string;
  chatModel: string;
  embeddingModel?: string;
  apiKeyLabel: string;
  apiKeyPlaceholder: string;
  modelsHint?: string;
  allowEmptyApiKey?: boolean;
};

export const MODEL_PROVIDER_PRESETS: ModelProviderPreset[] = [
  {
    id: "spark",
    name: "讯飞星火 Spark",
    description: "赛题出题企业相关 Provider，按 Spark HTTP OpenAI-compatible 接口接入。",
    baseUrl: "https://spark-api-open.xf-yun.com/v1",
    chatModel: "lite",
    apiKeyLabel: "API Key / APIPassword",
    apiKeyPlaceholder: "填入讯飞控制台的 APIPassword",
    modelsHint: "lite、generalv3、pro-128k、max-32k、4.0Ultra"
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek OpenAI-compatible 接口，适合通用问答和课程 RAG 回答。",
    baseUrl: "https://api.deepseek.com",
    chatModel: "deepseek-v4-pro",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 DeepSeek API Key"
  },
  {
    id: "qwen",
    name: "通义千问",
    description: "阿里百炼 OpenAI-compatible 接口，业务空间地址需要替换 WorkspaceId。",
    baseUrl: "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v4",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入百炼 API Key",
    modelsHint: "将 {WorkspaceId} 替换为你的业务空间 ID"
  },
  {
    id: "kimi",
    name: "Kimi",
    description: "Moonshot OpenAI-compatible 接口。",
    baseUrl: "https://api.moonshot.cn/v1",
    chatModel: "kimi-k2.6",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入 Moonshot API Key"
  },
  {
    id: "zhipu",
    name: "智谱 GLM",
    description: "智谱 OpenAI-compatible 接口。",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    chatModel: "glm-5.2",
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
    description: "硅基流动 OpenAI-compatible 接口。",
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
    name: "自定义兼容服务",
    description: "适合学校内网、私有网关或其它 OpenAI-compatible 服务。",
    baseUrl: "",
    chatModel: "",
    apiKeyLabel: "API Key",
    apiKeyPlaceholder: "填入服务商 API Key"
  }
];

export function getProviderPreset(presetId: string | null | undefined) {
  return MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId) ?? MODEL_PROVIDER_PRESETS[0];
}

export function inferProviderPresetId(baseUrl: string | null | undefined, presetId?: string | null) {
  if (presetId && MODEL_PROVIDER_PRESETS.some((preset) => preset.id === presetId)) {
    return presetId;
  }

  if (!baseUrl) {
    return "spark";
  }

  return MODEL_PROVIDER_PRESETS.find((preset) => preset.id !== "custom" && preset.baseUrl === baseUrl)?.id ?? "custom";
}
