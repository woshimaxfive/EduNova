# EduNova RAG 检索与引用设计

日期：2026-07-03

## 1. 当前阶段

Phase 5.2 已完成第一版课程知识库检索地基，Phase 5.3 已把检索结果接入课程会话引用持久化，Phase 6.1 已把命中引用的课程会话接入非流式真实模型回答：

- 已生成课程中的 `knowledge_chunks` 可以通过 `POST /api/v1/rag/search` 检索。
- 检索只在当前登录用户自己的课程内进行。
- 返回结果包含知识切片、课程资料、知识点、章节和匹配分数。
- 课程空间发送课程问题时，会通过课程会话调用真实检索，并把引用写入 assistant 消息的 `citation_json`。
- 刷新课程页或点击课程内历史后，前端从 `/tutor/sessions/{session_id}` 恢复消息和引用。
- 当课程问题命中引用且模型配置可用时，后端使用 OpenAI-compatible Chat Completions 基于引用生成回答，并保存到 assistant `content`。
- 当课程问题无引用时，不调用模型，继续返回资料依据不足。
- 当有引用但模型未配置时，保留引用并提示“已找到资料依据，但当前未配置可用模型。”

本阶段已接非流式真实模型回答，但仍不做 embedding、不做向量召回、不做流式输出。

## 2. 数据来源

Phase 5.2 到 Phase 6.2 只读取或复用现有数据表：

- `courses`：确认课程属于当前用户。
- `course_materials`：提供资料标题和资料来源。
- `knowledge_points`：提供知识点和章节上下文。
- `knowledge_chunks`：提供可检索文本切片。
- `chat_sessions`、`chat_messages`：保存课程会话消息和 assistant `citation_json`。
- `model_settings`：保存用户自己的 OpenAI-compatible 模型配置和加密 Key；Phase 6.2 起同一用户可保存多套配置，课程回答只使用当前默认配置，默认不存在时回退服务器 `.env`。

本阶段不新增数据库迁移，`knowledge_chunks.embedding` 继续允许为空。

## 3. 检索规则

当前检索采用确定性关键词评分：

1. 完整 query 命中权重最高。
2. 英文、数字和中文连续片段会被拆成检索词。
3. 中文长词会额外拆成二字片段，提高短问题命中率。
4. 中文查询按字符顺序覆盖给额外分数，避免“预估代价”和“高估代价”这类近似词完全打平。
5. 分数相同按 `chunk_id` 升序返回，保证结果稳定。

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
        "score": 9.5
      }
    ]
  },
  "trace_id": "trace_xxx"
}
```

## 5. 课程 RAG 回答生成

Phase 6.1 到 Phase 6.2 的课程回答生成规则：

- 只在 `scope=course` 会话中启用，不影响主页 `scope=home` 会话。
- 先检索课程 `knowledge_chunks`，再决定是否调用模型。
- prompt 只允许基于引用回答，要求说明依据，不允许编造资料外内容。
- assistant `content` 保存模型返回文本，`citation_json` 保留检索引用，`trace_id` 记录本次模型调用。
- 模型运行时配置解析为：当前用户默认配置优先，服务器 `.env` 兜底；非默认个人配置只在设置页保存、测试和切换默认时使用。
- 模型不可用、超时、鉴权失败、非 JSON 或空内容时返回可恢复错误，前端保留输入，不写入半截 assistant 消息。

## 6. 后续演进

Phase 6 后续继续演进：

- 为知识切片生成 embedding。
- 使用 pgvector 做向量召回。
- 将关键词召回和向量召回融合。
- 支持流式输出。
- 加入低依据提示和 ReviewAgent 审核。

Phase 5.2 的目标是让引用链路先真实存在，避免后续 AI 回答变成无来源的文本生成。Phase 5.3 则把这条引用链保存到课程会话里，保证刷新页面、切换课程历史后引用仍然可追溯。Phase 6.1 在此基础上接入真实模型，但继续把引用作为回答前提。
