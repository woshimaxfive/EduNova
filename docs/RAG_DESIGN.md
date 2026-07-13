# EduNova RAG 检索与引用设计

## 1. 当前目标

EduNova 的主页资料问答与课程问答共用同一套检索底座，但保持不同证据边界：

- 主页只检索当前用户在该会话中确认选择的资料，并允许模型使用通用知识。
- 课程空间只检索当前用户课程内的知识切片，回答必须受课程证据约束。
- 联网搜索仍由 `HomeTutorGraph.web_search` 调用 Tavily-compatible 服务，模型 Provider 不接管网页搜索。
- 引用只返回安全短片段、来源、章节、页码和检索状态，不返回完整资料、向量或模型输入。

## 2. 向量能力

向量连接与回答连接独立保存、独立测试、独立选择默认用途。当前支持：

| Provider | 协议 | 默认模型 | 维度 |
| --- | --- | --- | --- |
| 讯飞星火 | 原生签名 HTTP | LLM Embedding | 固定 2560 |
| 阿里云百炼 | OpenAI-compatible `/embeddings` | `text-embedding-v4` | 预设 1024，可按实际响应识别 |
| 硅基流动 | OpenAI-compatible `/embeddings` | `BAAI/bge-m3` | 1024 |
| 自定义服务 | OpenAI-compatible `/embeddings` | 用户填写 | 由连接测试和实际响应识别 |

讯飞资料使用 `domain=para`，问题使用 `domain=query`。单次输入超过 2KB 时按 UTF-8 字节边界安全拆分，分段向量做均值池化和归一化，不截断中文正文。

`knowledge_chunks.embedding` 和 `material_chunks.embedding` 使用无固定维度的 pgvector `vector`。每条向量同时记录：

- `embedding_provider`
- `embedding_model`
- `embedding_dimension`
- `embedding_profile_hash`
- `embedding_updated_at`

检索必须匹配用户、课程或资料、Provider、模型、维度和配置指纹。旧 1536 维向量保留为 legacy 数据，但缺少新配置指纹，不参与当前向量召回。

## 3. 混合召回与重排序

主页资料 RAG 和课程 RAG 使用同一流程：

1. 中文关键词召回 Top 30。
2. 当前向量配置可用时执行精确 cosine 向量召回 Top 30。
3. 使用 RRF 合并并去重为 Top 20 候选。
4. 当前重排序配置可用时执行 Rerank。
5. 返回最终 Top 5 引用。

当前重排序 Provider：

- 硅基流动 `/v1/rerank`，默认 `BAAI/bge-reranker-v2-m3`。
- 阿里云百炼 Workspace `/compatible-api/v1/reranks`，默认 `qwen3-rerank`。
- 自定义兼容重排序服务。

向量未配置或失败时退回关键词召回；重排序未配置、超时、限流或失败时退回 RRF 混合排序。系统不把内容自动转发给另一 Provider，也不把规则 fallback 宣称为语义向量或模型重排。

## 4. 向量重建

切换默认向量配置不会自动消耗额度。用户在设置页显式点击“重建向量索引”后，前端调用：

```text
POST /api/v1/settings/model/embedding/reindex-jobs
```

该任务复用 `AIJobRuntime`、Redis/RQ、进度、取消、刷新恢复和失败重试。任务只处理当前用户可访问的课程切片和资料切片，按批次更新向量与配置指纹；同一配置重复执行会覆盖对应切片的当前向量，不创建重复记录。

新资料和新课程仍会 best-effort 生成当前默认配置的向量。既有资料未重建时关键词召回始终可用，命中的缺失切片可在后续流程中渐进补齐。

## 5. 引用字段

引用在原有字段基础上可返回：

```json
{
  "retrieval_source": "keyword | vector | hybrid",
  "embedding_status": "external | local_fallback | provider_failed",
  "embedding_provider": "xfyun_embedding",
  "embedding_dimension": 2560,
  "rerank_score": 0.91,
  "rerank_status": "completed | not_configured | provider_failed"
}
```

`content` 或 `snippet` 始终是受长度限制的安全片段。Trace 只允许返回调用次数、候选数、实际维度、降级状态和安全错误类别，不记录查询全文、资料原文、向量、密钥或 Provider 原始响应。

## 6. X2-Flash 边界

回答默认预设为讯飞 Spark X2-Flash：

```text
base_url = https://spark-api-open.xf-yun.com/agent/v1/
model = spark-x
```

主页普通回答发送 `thinking.disabled`，开启深思时发送 `thinking.enabled`；其他 Graph 默认关闭 Provider 深度思考。Provider 只消费最终 `content`，忽略 `reasoning_content`。星火内置 `web_search` 不启用，保证网页来源继续由 EduNova 的 Tavily 节点、引用协议和 Agent trace 统一管理。

## 7. 验收边界

- 混合维度向量可以落库，但一次查询只使用当前配置指纹对应的同维向量。
- 连接测试保存实际向量维度，用户不手填维度。
- 无向量 Key 时课程问答和主页资料问答仍可使用关键词证据。
- 无重排序 Key 时混合召回仍可返回引用。
- 免费额度只在 UI 中提示“以服务商控制台为准”，不写死额度或承诺永久免费。
- 标准自动测试使用 Mock/Stub，不消耗真实 API Key。
