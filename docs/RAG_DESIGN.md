# EduNova RAG 检索与引用设计

日期：2026-07-04

## 1. 当前阶段

Phase 5.2 已完成第一版课程知识库检索地基，Phase 5.3 已把检索结果接入课程会话引用持久化，Phase 6.1 已把命中引用的课程会话接入非流式真实模型回答，Phase 6.3 已把课程空间回答切到流式输出，Phase 6.4 已把课程知识切片升级为 embedding 与混合检索：

- 已生成课程中的 `knowledge_chunks` 可以通过 `POST /api/v1/rag/search` 检索。
- 检索只在当前登录用户自己的课程内进行。
- 返回结果包含知识切片、课程资料、知识点、章节和匹配分数。
- 课程生成后会 best-effort 为 `knowledge_chunks.embedding` 写入 1536 维向量，RAG 搜索时也会懒加载补齐缺失或过期向量。
- 检索优先融合关键词分数和 cosine 相似度分数；无可用向量或外部 embedding 失败时回退关键词检索。
- 没有可用 embedding 配置或 Provider 失败时，课程 RAG 显式退回关键词检索；`local-hash-1536` 不参与课程语义向量命中。真实外部向量通过 pgvector SQL cosine 候选并与中文关键词合并排序。
- 课程空间发送课程问题时，会通过课程会话调用真实检索，并把引用写入 assistant 消息的 `citation_json`。
- 刷新课程页或点击课程内历史后，前端从 `/tutor/sessions/{session_id}` 恢复消息和引用。
- 当课程问题命中引用且模型配置可用时，后端使用 OpenAI-compatible Chat Completions 基于引用生成回答，并保存到 assistant `content`。
- 课程空间默认调用 `/api/v1/tutor/sessions/{session_id}/messages/stream`，先显示流式 token，完成后再用持久化消息替换临时状态。
- 当课程问题无引用时，不调用模型，继续返回资料依据不足。
- 当有引用但模型未配置时，保留引用并提示“已找到资料依据，但当前未配置可用模型。”
- 模型流式中途失败时返回 `error` 事件，不写入半截 assistant。

本阶段已接课程空间流式真实模型回答和第一版混合检索；讯飞原生 Embeddingp/Embeddingq、资源生成、多智能体编排和深度解析仍不在本轮范围内。

## 2. 数据来源

Phase 5.2 到 Phase 6.4 只读取或复用现有数据表：

- `courses`：确认课程属于当前用户。
- `course_materials`：提供资料标题和资料来源。
- `knowledge_points`：提供知识点和章节上下文。
- `knowledge_chunks`：提供可检索文本切片，并在 `embedding Vector(1536)` 保存 OpenAI-compatible 或本地 fallback 向量。
- `chat_sessions`、`chat_messages`：保存课程会话消息和 assistant `citation_json`。
- `model_settings`：保存用户自己的 OpenAI-compatible 模型配置和加密 Key；同一用户可分别选择回答默认与向量默认，课程回答和 Embedding 不要求共用 Provider、Base URL 或 Key。

本阶段不新增数据库迁移，继续复用既有 `knowledge_chunks.embedding Vector(1536)`。`metadata_json` 写入 `embedding_source`、`embedding_model`、`embedding_dimension`、`embedded_at`，用于识别本地 fallback、过期模型和后续重建。

## 3. 检索规则

当前检索采用混合评分：

1. 保留确定性关键词评分：完整 query 命中权重最高，英文、数字和中文连续片段会被拆成检索词，中文长词会额外拆成二字片段。
2. 查询有可用 embedding 时，对每个知识切片计算 cosine 相似度，负分归零后转换为 `vector_score`。
3. 最终 `score = keyword_score + vector_score`；纯向量命中达到阈值时也可以进入结果。
4. 课程生成时 best-effort 生成向量，搜索时对缺失或模型过期的向量做懒加载补齐。
5. 外部 embedding 失败时不阻断问答，`embedding_status` 暴露状态并退回关键词检索。
6. 分数相同按 `chunk_id` 升序返回，保证结果稳定。

无命中时返回空 `results`，前端显示资料不足提示，不伪造引用。

## 4. API 合同

正式接口：

```http
POST /api/v1/rag/search
Authorization: Bearer <token>
```

请求：

```json
{
  "course_id": 101,
  "query": "启发式搜索怎么复习？",
  "top_k": 5
}
```

响应：

```json
{
  "data": {
    "course_id": 101,
    "query": "启发式搜索怎么复习？",
    "top_k": 5,
    "retrieval_mode": "hybrid",
    "embedding_status": "local_fallback",
    "results": [
      {
        "chunk_id": 501,
        "course_id": 101,
        "material_id": 301,
        "knowledge_point_id": 401,
        "content": "启发式搜索利用启发函数估计路径代价。",
        "source_title": "人工智能导论讲义.md",
        "page_number": null,
        "section_title": "启发式搜索",
        "score": 9.5,
        "keyword_score": 5.2,
        "vector_score": 4.3,
        "retrieval_source": "hybrid",
        "embedding_status": "local_fallback"
      }
    ]
  },
  "trace_id": "trace_xxx"
}
```

## 5. 课程 RAG 回答生成

Phase 6.1 到 Phase 6.4 的课程回答生成规则：

- 只在 `scope=course` 会话中启用，不影响主页 `scope=home` 会话。
- 先用混合检索搜索课程 `knowledge_chunks`，再决定是否调用模型。
- prompt 只允许基于引用回答，要求说明依据，不允许编造资料外内容。
- assistant `content` 保存模型返回文本，`citation_json` 保留检索引用，`trace_id` 记录本次模型调用。
- 流式接口先返回 `metadata`，再通过多个 `token` 事件逐段返回文本，最后通过 `done` 返回最终 `TutorSessionDetail`。
- 只有 `done` 前完整生成成功，才持久化 user 消息、完整 assistant、引用和 `trace_id`。
- 回答运行时解析为：当前用户回答默认优先，服务器回答配置兜底；向量默认不会参与回答生成。
- 模型不可用、超时、鉴权失败、非 JSON、空内容或流式中途失败时返回可恢复错误，前端保留输入，不写入半截 assistant 消息。

## 6. Embedding 边界

Phase 6.4 的 embedding 规则：

- 优先使用当前用户向量默认配置中的 `embedding_model`，目标接口为该配置的 OpenAI-compatible `{base_url}/embeddings`；不存在个人向量默认时才回退服务器向量配置。
- 请求维度固定为 1536；如果服务不支持 `dimensions` 参数，Provider 会自动重试一次不带该字段。
- 返回向量长度必须为 1536，否则拒绝写入，避免破坏现有 `Vector(1536)` 合同。
- 如果没有可用 embedding 模型，使用 `local-hash-1536` 确定性本地 fallback，并在 API 和 UI 中明确展示。
- 不记录完整 API Key、JWT、完整 prompt 或资料全文。
- 讯飞星火聊天接口可走 OpenAI-compatible `/v1/chat/completions`，但讯飞原生 Embeddingp/Embeddingq 是独立授权、签名鉴权且返回 2560 维，本轮不接。

## 7. 后续演进

Phase 6 后续继续演进：

- 接入讯飞原生 Embeddingp/Embeddingq 或其他非 OpenAI-compatible embedding 专项。
- 在数据量变大后评估 pgvector 数据库侧近邻召回和批量重建任务。
- 加入低依据提示和 ReviewAgent 审核。
- 接入资源生成、多智能体编排和学习评估链路。

Phase 5.2 的目标是让引用链路先真实存在，避免后续 AI 回答变成无来源的文本生成。Phase 5.3 则把这条引用链保存到课程会话里，保证刷新页面、切换课程历史后引用仍然可追溯。Phase 6.1 在此基础上接入真实模型，Phase 6.3 补上课程空间流式体验，Phase 6.4 再把引用召回从关键词检索升级为可解释的混合检索。
