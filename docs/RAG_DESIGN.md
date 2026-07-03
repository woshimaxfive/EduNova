# EduNova RAG 检索与引用设计

日期：2026-07-03

## 1. 当前阶段

Phase 5.2 已完成第一版课程知识库检索地基：

- 已生成课程中的 `knowledge_chunks` 可以通过 `POST /api/v1/rag/search` 检索。
- 检索只在当前登录用户自己的课程内进行。
- 返回结果包含知识切片、课程资料、知识点、章节和匹配分数。
- 课程空间发送课程问题时，会先调用真实检索接口，并在回答下方展示真实引用片段。

本阶段不接真实大模型，不生成最终 AI 回答，不做 embedding，不做向量召回。

## 2. 数据来源

Phase 5.2 只读取现有数据表：

- `courses`：确认课程属于当前用户。
- `course_materials`：提供资料标题和资料来源。
- `knowledge_points`：提供知识点和章节上下文。
- `knowledge_chunks`：提供可检索文本切片。

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

## 5. 后续演进

Phase 6 再进入真实 RAG 生成：

- 接模型 Provider。
- 为知识切片生成 embedding。
- 使用 pgvector 做向量召回。
- 将关键词召回和向量召回融合。
- 让 AI 回答基于检索结果生成，并保留引用。
- 加入低依据提示和 ReviewAgent 审核。

Phase 5.2 的目标是让引用链路先真实存在，避免后续 AI 回答变成无来源的文本生成。
