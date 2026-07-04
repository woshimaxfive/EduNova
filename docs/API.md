# EduNova API 设计

日期：2026-07-01

## 1. 设计目标

本文档定义 EduNova 第一版前后端接口约定。接口设计以学生学习主链路为中心，兼顾 演示模式、RAG 引用、多智能体轨迹和后续开源部署。

接口基础路径：

```text
/api/v1
```

健康检查路径：

```text
/api/health
```

## 2. 通用约定

### 2.0 前端合同模块

当前前端已按本文档拆出 `frontend/src/api/` 合同模块。Axios 默认基础路径为：

```text
/api/v1
```

前端模块只负责路径、请求参数和响应类型约定，不在模块内塞业务编排。

当前后端已经挂载的 `/api/v1` router 为：

```text
auth
dashboard
courses
materials
profiles
rag
tutor
settings
```

当前前端仍保留以下合同常量，方便后续 Phase 接入，但它们不是当前已经挂载的后端 router，不能在页面或文档中当作已实现接口：

```text
resources
agents
paths
practice
reports
demo
```

这些模块已有 Vitest 合同测试，用于防止路径和基础路径漂移。

### 2.1 认证方式

登录成功后，前端在请求头中携带 JWT：

```text
Authorization: Bearer <token>
```

未登录或 token 无效返回 401。

### 2.2 时间格式

所有时间使用 ISO 8601 字符串：

```text
2026-07-01T10:30:00+08:00
```

### 2.3 成功响应

单对象响应：

```json
{
  "data": {},
  "trace_id": "trace_20260701_001"
}
```

列表响应：

```json
{
  "data": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "trace_id": "trace_20260701_001"
}
```

### 2.4 错误响应

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数不正确",
    "details": {}
  },
  "trace_id": "trace_20260701_001"
}
```

### 2.5 常用错误码

| 错误码 | HTTP 状态 | 说明 |
| --- | --- | --- |
| `UNAUTHORIZED` | 401 | 未登录或 token 无效 |
| `FORBIDDEN` | 403 | 无权限访问 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `VALIDATION_ERROR` | 422 | 参数校验失败 |
| `DUPLICATE_RESOURCE` | 409 | 重复资源 |
| `UNSUPPORTED_FILE_TYPE` | 400 | 不支持的文件类型 |
| `CONFIGURATION_ERROR` | 500 | 服务端配置缺失或不可用 |
| `MODEL_PROVIDER_ERROR` | 502 | 模型服务异常 |
| `INSUFFICIENT_EVIDENCE` | 200 | 资料依据不足，正常返回但标记低依据 |
| `TASK_FAILED` | 500 | 长任务失败 |

## 3. 健康检查

### GET `/api/health`

用途：检查后端服务是否运行。

响应：

```json
{
  "status": "ok",
  "service": "edunova-api"
}
```

## 4. Auth 接口

### POST `/auth/register`

用途：注册学生账号。

请求：

```json
{
  "email": "student@example.com",
  "password": "Password123",
  "display_name": "小新",
  "starter_mode": "ai_intro"
}
```

`starter_mode` 用于决定新账号首次进入学习空间时是否带示例内容：

- `blank`：空白开始，不自动创建内置课程、资料和主页历史。
- `ai_intro`：复制“人工智能导论”示例课程、示例资料、知识点和知识切片到当前用户空间。

如果前端没有传入，后端默认按 `ai_intro` 处理，保证比赛演示和初次试用有可见主链路。该字段不能指向共享演示账号，也不能复用其他用户资料。

注册接口只返回用户对象，不直接返回 token。前端注册成功后再调用登录接口写入本地 session；如果自动登录失败，跳回登录页提示用户重新登录。

响应：

```json
{
  "data": {
    "id": 1,
    "email": "student@example.com",
    "display_name": "小新",
    "role": "student",
    "starter_mode": "ai_intro"
  },
  "trace_id": "trace_20260701_001"
}
```

### POST `/auth/login`

用途：登录。

请求：

```json
{
  "email": "student@example.com",
  "password": "Password123"
}
```

响应：

```json
{
  "data": {
    "access_token": "jwt-token",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "email": "student@example.com",
      "display_name": "小新",
      "role": "student",
      "starter_mode": "ai_intro"
    }
  },
  "trace_id": "trace_20260701_002"
}
```

### GET `/auth/me`

用途：读取当前用户。

响应：

```json
{
  "data": {
    "id": 1,
    "email": "student@example.com",
    "display_name": "小新",
    "role": "student",
    "starter_mode": "ai_intro"
  },
  "trace_id": "trace_20260701_003"
}
```

### POST `/auth/logout`

用途：退出登录。第一版前端清理 token，后端返回成功。

响应：

```json
{
  "data": {
    "ok": true
  },
  "trace_id": "trace_20260701_004"
}
```

## 5. Learning Space Summary 接口

### GET `/dashboard/summary`

用途：获取 AI 学习主页首屏总览。Phase 4.2 已实现该接口，要求携带 JWT，只读取当前登录用户自己的课程、个人资料库资料、主页会话、画像和资源记录。Phase 4.4 后，主页资料库浮层和资料库摘要读取独立 `materials` 表，不再读取前端静态资料。该接口服务贴边可收起历史侧栏、侧栏账号入口、输入框建议、发送后主页对话态、输入区资料库浮层入口、文件上传入口、联网搜索/深度思考工具状态和最近学习轻量列表，不默认绑定某一门课程。

响应包含：

- 画像摘要。
- 主页最近对话。
- 最近课程或最近学习空间。
- 资料库摘要，默认不自动选中资料；前端点选后才作为本次对话参考。
- 最近资料列表。
- 最近资源列表。
- 输入框快捷建议。
- 证据层摘要。
- 空状态类型和文案。

阶段边界：

- `blank` 注册用户返回空课程、空资料、空主页历史和 `empty_state.kind=blank`。
- `ai_intro` 注册用户返回复制到该用户空间的人工智能导论课程和资料，不返回共享系统模板。
- 课程进度只显示真实进度；没有进度记录时显示“未开始”，不使用前端写死的演示百分比。
- 本接口不创建会话、不上传资料、不触发 AI/RAG，也不生成课程。

响应示例：

```json
{
  "data": {
    "profile_summary": {
      "display_name": "小新",
      "starter_mode": "ai_intro",
      "has_profile": true,
      "knowledge_foundation": "机器学习入门",
      "learning_goal": "期末前掌握神经网络"
    },
    "recent_conversations": [
      {
        "id": "501",
        "title": "期末复习怎么开始",
        "meta": "刚刚",
        "scope": "home",
        "updated_at": "2026-07-03T11:57:00Z"
      }
    ],
    "recent_courses": [
      {
        "id": "101",
        "title": "人工智能导论",
        "source_type": "builtin",
        "progress_label": "未开始",
        "focus": "人工智能",
        "next": "开始学习"
      }
    ],
    "material_library_summary": {
      "material_count": 1,
      "unassigned_count": 0
    },
    "recent_materials": [
      {
        "id": "201",
        "title": "人工智能导论讲义.md",
        "type": "MD",
        "detail": "已解析",
        "modified": "今天",
        "size": "12 KB"
      }
    ],
    "recent_resources": [],
    "command_suggestions": [
      "帮我复习人工智能导论",
      "把反向传播讲到我能做题",
      "用这些资料生成期末复习课"
    ],
    "evidence_summary": {
      "citation_count": 0,
      "latest_trace_id": null,
      "low_evidence_count": 0
    },
    "empty_state": {
      "kind": "starter",
      "title": "从人工智能导论开始",
      "description": "内置课程已经进入你的个人空间，可以直接开始学习。",
      "action_label": "开始学习"
    }
  },
  "trace_id": "trace_20260701_004"
}
```

## 6. Profile 接口

状态：Phase 7.1 已实现。当前后端已挂载 `profiles` router，`ProfilePage` 从真实后端读取画像和画像事件。画像采用确定性抽取，不新增外部模型调用。

### GET `/profiles/me`

用途：读取当前学生画像。

规则：

- 必须携带 JWT，只读取当前用户自己的画像。
- 空画像也返回稳定 8 维结构，字符串字段为空字符串，`weak_points=[]`。
- `version` 由当前画像关联的画像事件数量派生。
- `next_question` 用于前端画像对话入口，不等同于强制问卷。

响应：

```json
{
  "data": {
    "id": "1",
    "version": 3,
    "has_profile": true,
    "profile_json": {
      "major_background": "计算机专业大二",
      "knowledge_foundation": "机器学习刚入门",
      "learning_goal": "掌握神经网络和反向传播",
      "cognitive_style": "案例驱动",
      "learning_preference": "图解和代码",
      "weak_points": ["高等数学", "链式法则"],
      "learning_pace": "期末前冲刺",
      "motivation_interest": "希望提升 AI 实践能力"
    },
    "confidence_score": 72,
    "updated_reason": "更新学习画像：学习目标、知识基础",
    "updated_at": "2026-07-05T09:00:00Z",
    "next_question": "这门课你最担心哪一章？"
  },
  "trace_id": "trace_profile_me"
}
```

### POST `/profiles/chat`

用途：通过对话更新学习画像。Phase 7.1 使用确定性规则抽取 8 维画像，写入 `student_profiles` 并追加 `profile_events`。

请求：

```json
{
  "message": "我是计算机专业大二学生，机器学习刚入门，数学基础一般，想期末前掌握神经网络。"
}
```

响应包含回复、最新画像和本次画像事件：

```json
{
  "data": {
    "reply": "已更新你的学习画像。",
    "profile": {},
    "event": {
      "id": "10",
      "dimension": "profile_chat",
      "change_summary": "更新学习画像：学习目标、薄弱点",
      "evidence_json": {
        "source_type": "profile_chat",
        "summary": "学生画像对话",
        "updated_dimensions": ["learning_goal", "weak_points"]
      },
      "created_at": "2026-07-05T09:01:00Z"
    }
  },
  "trace_id": "trace_profile_chat"
}
```

### GET `/profiles/events`

用途：查看画像变化记录。

规则：

- 只返回当前用户画像事件，默认最近 20 条。
- 课程问答产生的画像候选事件会使用 `dimension="weak_points"`。
- 课程问答事件的 `evidence_json` 只保存 `source_type`、`course_id`、`session_id`、消息 ID、`trace_id` 和引用摘要；不保存完整用户问题、系统提示词、模型输入或资料原文。

## 7. Course 接口

### GET `/courses`

用途：获取我的课程列表。Phase 5.1 已实现，必须携带 JWT，只返回当前用户拥有或已加入的课程。

查询参数：

- `source_type`：`builtin`、`uploaded`。

响应元素：

```json
{
  "id": "101",
  "title": "机器学习期末复习",
  "description": "由 2 份资料生成",
  "subject": "自主学习",
  "source_type": "uploaded",
  "status": "ready",
  "progress_percent": 0,
  "material_count": 2,
  "knowledge_point_count": 6,
  "chunk_count": 18
}
```

### GET `/courses/{course_id}`

用途：获取课程详情。Phase 5.1 已实现，只允许访问当前用户自己的课程。

### GET `/courses/{course_id}/overview`

用途：获取课程概览、章节和知识点。Phase 5.1 已实现。

### GET `/courses/{course_id}/knowledge-points`

用途：获取课程知识点。Phase 5.1 已实现。

响应元素：

```json
{
  "id": "9001",
  "title": "梯度下降",
  "summary": "理解梯度方向和学习率。",
  "chapter": "优化方法",
  "order_index": 1,
  "difficulty": "基础"
}
```

### GET `/courses/{course_id}/mastery-map`

用途：获取知识点掌握地图。当前未实现，后续由掌握度和练习评估阶段接入。

响应包含：

- 知识点。
- 掌握状态。
- 先修关系。
- 推荐复习标记。

## 8. Materials 接口

### POST `/materials/upload`

用途：上传资料到当前登录用户的个人资料库。Phase 4.4 已实现，必须携带 JWT。资料可以暂不属于任何课程，也可以在上传时通过 `course_id` 加入当前用户自己的课程；后续可作为主页对话参考、加入已有课程或用于生成新课程。

请求类型：`multipart/form-data`

字段：

- `course_id`：可选。传入时表示上传后同时加入该课程；不传时仅进入个人资料库。
- `file`：上传文件。

支持类型：

- TXT、Markdown：轻解析为 `completed`，保存原文到 `extracted_text`。
- PDF、DOC、DOCX、PPT、PPTX：仅入库为 `uploaded`，暂不做正文解析。
- PNG、JPG、JPEG、WEBP：仅入库为 `uploaded`，提示“仅入库，暂不做 OCR”。

响应：

```json
{
  "data": {
    "id": "1",
    "material_id": 1,
    "course_id": null,
    "filename": "ai-notes.md",
    "title": "ai-notes.md",
    "type": "MD",
    "detail": "已解析",
    "modified": "刚刚",
    "size": "2 KB",
    "parse_status": "completed"
  },
  "trace_id": "trace_20260701_006"
}
```

边界：

- 单文件大小受 `MATERIAL_MAX_UPLOAD_MB` 限制，默认 25 MB。
- 文件保存到 `MATERIAL_STORAGE_DIR` 下的用户隔离目录，数据库只保存相对路径。
- 不支持的扩展名返回 400。
- `course_id` 不属于当前用户时返回 404 或 403。

### GET `/materials/{material_id}`

用途：查看当前用户资料详情。只能访问自己的资料。

响应：

```json
{
  "data": {
    "id": "1",
    "title": "ai-notes.md",
    "type": "MD",
    "detail": "已解析",
    "modified": "今天",
    "size": "2 KB",
    "category": "document",
    "extension": "MD",
    "parse_status": "completed",
    "course_ids": [],
    "filename": "ai-notes.md",
    "content_type": "text/markdown",
    "extracted_text_preview": "第一章 人工智能导论..."
  },
  "trace_id": "trace_20260701_007"
}
```

### GET `/materials`

用途：查看当前用户个人资料库。Phase 4.4 已实现，支持筛选未归属课程资料、某课程已关联资料和最近上传资料。`/app/library` 通过该接口渲染文件库式列表；主页资料库浮层通过 `/dashboard/summary.recent_materials` 渲染最近资料。

查询参数：

- `course_id`：可选，传入时查看某课程资料。
- `unassigned`：可选，查看未加入任何课程的资料。

响应：

```json
{
  "data": [
    {
      "id": "1",
      "title": "ai-notes.md",
      "type": "MD",
      "detail": "已解析",
      "modified": "今天",
      "size": "2 KB",
      "category": "document",
      "extension": "MD",
      "parse_status": "completed",
      "course_ids": []
    }
  ],
  "trace_id": "trace_20260701_008"
}
```

### POST `/courses/{course_id}/materials`

用途：把资料库中的一个或多个资料加入当前用户已有课程。Phase 4.4 已实现，使用 `course_material_links` 关联关系，不复制原文件；重复关联不会重复插入。

请求：

```json
{
  "material_ids": [1, 2]
}
```

响应：

```json
{
  "data": {
    "course_id": "1",
    "material_ids": ["1", "2"],
    "attached_count": 2
  },
  "trace_id": "trace_20260701_009"
}
```

### GET `/materials/{material_id}/progress`

用途：查看资料解析进度。Phase 4.4 只返回资料入库/轻解析状态，不返回真实建课进度。

响应：

```json
{
  "data": {
    "status": "completed",
    "progress_percent": 100,
    "message": "资料已完成轻解析"
  },
  "trace_id": "trace_20260701_010"
}
```

### POST `/courses/from-materials`

用途：根据资料库中的一个或多个资料生成课程。Phase 5.1 已实现，必须携带 JWT。当前只支持当前用户个人资料库里 `parse_status=completed` 且已有 `extracted_text` 的 TXT/Markdown 资料；PDF/DOCX/PPTX/图片会返回 400，提示“当前仅支持已解析的 TXT/Markdown 生成课程”。

请求：

```json
{
  "material_ids": [1, 2],
  "course_title": "机器学习期末复习"
}
```

响应：

```json
{
  "data": {
    "course": {
      "id": "101",
      "title": "机器学习期末复习",
      "description": "由 2 份资料生成",
      "subject": "自主学习",
      "source_type": "uploaded",
      "status": "ready",
      "progress_percent": 0,
      "material_count": 2,
      "knowledge_point_count": 6,
      "chunk_count": 18
    },
    "knowledge_points": [
      {
        "id": "9001",
        "title": "第一章 绪论",
        "summary": "由资料内容生成的课程知识点摘要。",
        "chapter": "第一章 绪论",
        "order_index": 1,
        "difficulty": "基础"
      }
    ]
  },
  "trace_id": "trace_20260703_course_001"
}
```

生成规则：

- Markdown 的 `#`、`##`、`###` 标题优先生成章节和知识点。
- TXT 无标题时按段落生成“第 1 部分 / 第 2 部分”等知识点。
- 后端会创建 `Course`、`CourseEnrollment`、兼容旧链路的 `CourseMaterial`、`CourseMaterialLink`、`KnowledgePoint` 和 `KnowledgeChunk`。
- Phase 6.4 后，课程生成会 best-effort 为新 `KnowledgeChunk` 写入 1536 维 embedding；外部 embedding 失败不阻断建课，后续 `/rag/search` 会再尝试懒加载补齐。
- `knowledge_chunks.metadata_json` 会记录 `embedding_source`、`embedding_model`、`embedding_dimension`、`embedded_at`，便于识别本地 fallback、过期模型和后续重建。
- 前端 `/app` 主页资料库浮层和 `/app/library` 使用同一接口；成功后刷新 summary/materials 并跳转 `/app/courses/{course_id}`。

### POST `/materials/compare`

用途：对比多份资料并提炼考点。Phase 4.4 未实现。

请求：

```json
{
  "course_id": 1,
  "material_ids": [1, 2, 3]
}
```

响应包含高频考点、重复概念、遗漏点和引用来源。

## 9. RAG 接口

### POST `/rag/search`

用途：检索课程知识库。Phase 5.2 已实现受保护检索，Phase 6.4 已升级为关键词/向量混合召回。接口必须携带 JWT，只能检索当前用户自己的课程；检索本身不调用聊天大模型。

请求：

```json
{
  "course_id": 1,
  "query": "启发式搜索和盲目搜索有什么区别？",
  "top_k": 5
}
```

响应：

```json
{
  "data": {
    "course_id": 1,
    "query": "启发式搜索和盲目搜索有什么区别？",
    "top_k": 5,
    "retrieval_mode": "hybrid",
    "embedding_status": "local_fallback",
    "results": [
      {
        "chunk_id": 1,
        "course_id": 1,
        "material_id": 1,
        "knowledge_point_id": 2,
        "content": "启发式搜索利用启发函数估计路径代价。",
        "source_title": "人工智能导论讲义",
        "page_number": 12,
        "section_title": "启发式搜索",
        "score": 8.42,
        "keyword_score": 4.2,
        "vector_score": 4.22,
        "retrieval_source": "hybrid",
        "embedding_status": "local_fallback"
      }
    ]
  },
  "trace_id": "trace_20260701_008"
}
```

规则：

- `top_k` 范围为 1 到 10，默认 5。
- 空 query 返回校验错误。
- 无 token 返回 401。
- 访问他人课程返回 404。
- 无命中时 `results=[]`，前端必须显示资料不足，不得伪造引用。
- Phase 6.4 后，后端会优先使用当前用户默认模型配置中的 `embedding_model` 调用 OpenAI-compatible `{base_url}/embeddings`，请求维度为 1536；如果服务不支持 `dimensions` 参数，会自动重试一次不带该字段。
- 如果用户默认配置和服务器兜底都没有可用 embedding 模型，后端会使用显式标记的 `local-hash-1536` 确定性 fallback，保证开源和测试环境仍可检索；前端必须把它显示为本地 fallback，不能伪装成真实语义向量。
- 外部 embedding 失败时不阻断问答，接口会退回关键词检索并通过 `embedding_status` 暴露状态。
- 本轮不接讯飞原生 Embeddingp/Embeddingq；其独立授权、签名鉴权和 2560 维输出放到后续专项。

## 10. Resource 接口

状态：后续预留。当前后端未挂载 `resources` router，`StudioPage` 只提供资源工坊前端骨架和本地预备交互。

### POST `/resources/generate`

用途：生成个性化学习资源。

请求：

```json
{
  "course_id": 1,
  "knowledge_point_id": 8,
  "resource_types": ["doc", "mindmap", "quiz", "code", "slide"],
  "learning_goal": "理解反向传播",
  "difficulty": "medium"
}
```

响应：

```json
{
  "data": {
    "trace_id": "trace_20260701_resource_001",
    "resources": [
      {
        "id": 1,
        "resource_type": "doc",
        "title": "反向传播个性化讲解",
        "review_status": "passed",
        "confidence_score": 0.91,
        "citation_refs": []
      }
    ]
  },
  "trace_id": "trace_20260701_009"
}
```

### GET `/resources`

用途：获取资源列表。

### GET `/resources/{resource_id}`

用途：获取资源详情。

### GET `/resources/{resource_id}/quality`

用途：获取资源质量评分。

## 11. Agent Trace 接口

状态：后续预留。当前后端未挂载 `agents` router；课程问答会返回 `trace_id` 和引用，但完整多智能体轨迹查询还未实现。

### GET `/agents/traces/{trace_id}`

用途：获取某次多智能体任务轨迹。

响应：

```json
{
  "data": {
    "trace_id": "trace_20260701_resource_001",
    "logs": [
      {
        "agent_name": "ProfileAgent",
        "step_index": 1,
        "status": "success",
        "duration_ms": 120,
        "input_summary": "读取学生画像",
        "output_summary": "识别学生偏好案例学习",
        "review_status": null
      }
    ]
  },
  "trace_id": "trace_20260701_010"
}
```

## 12. Learning Path 接口

状态：后续预留。当前后端未挂载 `paths` router，`/app/path` 仍展示前端学习路径骨架。

### POST `/paths/generate`

用途：生成个性化学习路径。

请求：

```json
{
  "course_id": 1,
  "duration_days": 7,
  "goal": "期末复习神经网络"
}
```

### GET `/paths/current`

用途：获取当前学习路径。

### PATCH `/paths/tasks/{task_id}`

用途：更新任务状态。

请求：

```json
{
  "status": "completed"
}
```

## 13. Tutor 接口

### POST `/tutor/sessions`

用途：创建 AI 学习会话。Phase 3 重定向后，会话分为主页会话和课程会话。Phase 4.3 已实现主页会话，Phase 5.3 已把课程会话接入课程空间；必须携带 JWT，只能创建当前登录用户自己的会话。

请求：

```json
{
  "scope": "course",
  "course_id": 1,
  "mode": "socratic",
  "title": "反向传播答疑"
}
```

主页会话示例：

```json
{
  "scope": "home",
  "course_id": null,
  "mode": "chat",
  "title": "帮我整理这份期末资料"
}
```

规则：

- `scope=home` 时 `course_id` 必须为空，当前 `/app` 首页首次发送会先创建主页会话。
- `scope=course` 时必须传 `course_id`，且课程必须属于当前登录用户。
- `scope=course` 已用于 `/app/courses/:courseId`，课程空间首次提问会先创建课程会话，连续追问复用当前课程会话。
- 会话标题由前端用第一条问题截取生成，也可以由调用方显式传入。
- 主页会话可以后续移入课程，移入后应从主页历史中消失或标记为已归档。

响应：

```json
{
  "data": {
    "id": "12",
    "scope": "home",
    "course_id": null,
    "title": "帮我整理这份期末资料",
    "mode": "chat",
    "archived_from_home": false,
    "created_at": "2026-07-03T08:00:00Z",
    "updated_at": "2026-07-03T08:00:00Z"
  },
  "trace_id": "trace_xxx"
}
```

### GET `/tutor/sessions`

用途：查看会话列表。支持按 `scope` 和 `course_id` 筛选主页历史或课程内历史。Phase 4.3 已接入 `scope=home`，用于左侧主页历史；Phase 5.3 已接入 `scope=course&course_id=...`，用于课程空间侧栏和课程内历史；只返回当前用户自己的会话。

查询参数：

- `scope`：`home` 或 `course`，默认 `home`。
- `course_id`：课程会话筛选参数，主页历史不传。

### GET `/tutor/sessions/{session_id}`

用途：查看会话详情。Phase 4.3 已用于点击左侧主页历史后恢复主页消息列表；Phase 5.3 已用于点击课程内历史后恢复课程消息和 `citation_json` 引用。只能访问当前用户自己的会话。

响应：

```json
{
  "data": {
    "session": {
      "id": "12",
      "scope": "home",
      "course_id": null,
      "title": "帮我整理这份期末资料",
      "mode": "chat",
      "archived_from_home": false,
      "created_at": "2026-07-03T08:00:00Z",
      "updated_at": "2026-07-03T08:03:00Z"
    },
    "messages": [
      {
        "id": "21",
        "session_id": "12",
        "role": "user",
        "content": "为什么反向传播要用链式法则？",
        "citation_json": [],
        "trace_id": null,
        "created_at": "2026-07-03T08:01:00Z"
      }
    ]
  },
  "trace_id": "trace_xxx"
}
```

### POST `/tutor/sessions/{session_id}/messages`

用途：发送问题并获取回答。Phase 4.3 已实现主页会话持久化闭环：写入一条 `user` 消息，并同步写入一条 `assistant` 回复。当前 `scope=home` 会调用当前用户默认模型配置生成普通学习回答，用户配置不存在时回退服务器 `.env` 配置；主页不做资料 RAG、不做真实联网搜索、不做流式输出。Phase 5.3 后，如果目标 session 是 `scope=course`，后端会先基于当前课程调用 RAG 检索，把命中结果写入 assistant 消息的 `citation_json`；如果无命中则写入空引用并提示资料依据不足。Phase 6.1 后，课程会话在命中引用且模型配置可用时，会通过 OpenAI-compatible Chat Completions 生成非流式真实回答。Phase 6.3 后，课程空间前端默认优先使用流式接口，本接口保留为兼容路径和自动化测试路径。Phase 6.4 后，课程 RAG 默认使用关键词/向量混合检索，旧关键词字段继续兼容。

请求：

```json
{
  "message": "为什么反向传播要用链式法则？"
}
```

当前响应返回完整会话详情。

主页会话规则：

- assistant 内容来自普通模型回答；无可用模型配置时保存清晰提示。
- `citation_json=[]`；模型成功时 `trace_id` 写入本次模型调用 trace，未配置模型时为 `null`。
- 不调用课程 RAG，不读取已选资料内容，不伪造引用。
- 联网搜索和深度思考仍是前端预备开关，本接口不会因为按钮高亮而进行真实联网搜索或推理参数透传。
- 模型调用失败时返回可恢复错误，不写入半截 assistant 消息。

课程会话规则：

- 命中课程知识切片时，assistant `citation_json` 采用 `/rag/search` 的结果字段结构：`chunk_id`、`course_id`、`material_id`、`knowledge_point_id`、`content`、`source_title`、`page_number`、`section_title`、`score`；Phase 6.4 后可额外包含 `keyword_score`、`vector_score`、`retrieval_source`、`embedding_status`。
- 无命中时 `citation_json=[]`，assistant 内容提示“资料依据不足”，前端不得伪造引用。
- 有命中且可解析模型配置时，assistant `content` 保存模型基于引用生成的回答，`trace_id` 写入本次模型调用 trace。
- 有命中但无可用模型配置时，assistant 保存“已找到资料依据，但当前未配置可用模型。”，引用仍保留。
- 模型调用超时、鉴权失败、非 JSON、空内容或流式中途失败时返回 `MODEL_PROVIDER_ERROR`，前端保留输入，不写入半截 assistant 消息。
- 课程空间刷新后，前端通过 `GET /tutor/sessions/{session_id}` 恢复消息和引用。

低依据评分、完整 agent trace 和 ReviewAgent 仍在后续阶段接入；embedding 与混合召回已在 Phase 6.4 接入，讯飞原生 2560 维 Embedding 仍未接入。

### POST `/tutor/sessions/{session_id}/messages/stream`

用途：SSE 流式返回课程空间回答。Phase 6.3 已实现，必须携带 JWT，只允许 `scope=course` 会话调用；主页 `scope=home` 调用返回 400。请求体沿用普通消息接口：

```json
{
  "message": "启发式搜索怎么复习？"
}
```

响应类型：

```text
Content-Type: text/event-stream
```

事件顺序：

```text
event: metadata
data: {"session_id":"12","trace_id":"trace_xxx","citation_count":2,"used_model":true}

event: token
data: {"content":"可以先从启发函数的作用看起。"}

event: done
data: {"session":{},"messages":[]}
```

错误事件：

```text
event: error
data: {"code":"MODEL_PROVIDER_ERROR","message":"模型暂不可用，请检查设置或稍后重试。"}
```

流式规则：

- 后端先检索课程知识切片，再决定是否调用模型；Phase 6.4 后检索优先走混合召回，失败时退回关键词检索。
- 无引用时不调用模型，流式返回“资料依据不足”，并持久化 user 消息和 assistant 提示，`citation_json=[]`。
- 有引用但未配置可用模型时不调用外部模型，流式返回未配置提示，仍持久化真实引用。
- 有引用且模型可用时，Provider 以 `stream=true` 调用 `{base_url}/chat/completions`，逐段解析 `data: {...}` 和 `[DONE]`。
- 只有流式成功完成后，后端才持久化 user 消息、完整 assistant 回答、真实引用和 `trace_id`。
- 模型流式中途失败时只发送 `error` 事件，不写入半截 assistant；前端必须保留输入并提示用户检查设置或稍后重试。
- `done` 事件返回最终 `TutorSessionDetail`，前端用它替换临时流式状态并刷新课程历史。

## 14. Practice 与 Report 接口

状态：后续预留。当前后端未挂载 `practice` 与 `reports` router，练习和报告页面仍是前端骨架和本地预备交互。

### POST `/practice/sessions`

用途：创建练习。

请求：

```json
{
  "course_id": 1,
  "knowledge_point_ids": [8],
  "question_count": 5,
  "difficulty": "medium"
}
```

### GET `/practice/sessions/{session_id}`

用途：查看练习题。

### POST `/practice/sessions/{session_id}/answers`

用途：提交答案。

请求：

```json
{
  "answers": [
    {
      "question_id": "q1",
      "answer_text": "链式法则用于计算复合函数梯度"
    }
  ]
}
```

### POST `/reports/generate`

用途：生成学习报告。

请求：

```json
{
  "course_id": 1,
  "practice_session_id": 1
}
```

### GET `/reports/latest`

用途：获取最新学习报告。

## 15. Weakness Review 接口

### GET `/weakness-review-queue`

用途：查看薄弱点复习队列。

### POST `/weakness-review-queue/{item_id}/start`

用途：开始某个薄弱点复习任务。

## 16. Exam Sprint 接口

### POST `/exam-sprint/plans`

用途：生成期末冲刺计划。

请求：

```json
{
  "course_id": 1,
  "duration_days": 7,
  "material_ids": [1, 2],
  "goal": "复习人工智能导论期末考试"
}
```

### GET `/exam-sprint/plans/{plan_id}`

用途：查看冲刺计划。

## 17. Export 接口

### POST `/exports/learning-dossier`

用途：导出 Markdown 学习档案。

请求：

```json
{
  "course_id": 1
}
```

### GET `/exports/{job_id}`

用途：查看导出状态和下载地址。

## 18. Demo 接口

### POST `/demo/reset`

用途：重置演示数据。

响应：

```json
{
  "data": {
    "email": "demo@edunova.local",
    "password_hint": "Demo123456",
    "reset": true
  },
  "trace_id": "trace_20260701_011"
}
```

### GET `/demo/status`

用途：查看演示数据状态。

## 19. Settings 接口

### GET `/settings/model`

用途：获取当前模型设置摘要。Phase 6.2 后该接口作为兼容接口保留，读取当前用户默认模型配置；没有默认配置时回退 `.env` 中的系统模型配置；如果两者都不可用，返回 `source=none` 和 `can_use_model=false`。响应不会返回明文 API Key。前端 Provider 预设首位为讯飞星火 Spark，但后端协议仍统一保存为 `openai_compatible`。

响应：

```json
{
  "data": {
    "source": "user",
    "provider": "openai_compatible",
    "base_url": "https://api.example.com/v1",
    "chat_model": "gpt-4.1-mini",
    "embedding_model": null,
    "has_api_key": true,
    "api_key_masked": "sk-u...cret",
    "can_use_model": true
  },
  "trace_id": "trace_settings_001"
}
```

### PUT `/settings/model`

用途：保存当前用户默认 OpenAI-compatible 模型设置。Phase 6.2 后该接口作为兼容接口保留：如果当前用户已有默认配置，则更新默认配置；如果没有个人配置，则创建一条默认配置。用户 API Key 使用 Fernet 加密后写入 `model_settings.api_key_ciphertext`；没有 `MODEL_SETTINGS_ENCRYPTION_KEY` 时，保存非空 Key 返回 `CONFIGURATION_ERROR`。`api_key` 为空字符串或缺省时保留原密钥。`embedding_model` 当前可选；Phase 6.4 后若填写则用于 OpenAI-compatible `{base_url}/embeddings`，若缺省则自动使用显式本地 fallback。

请求：

```json
{
  "provider": "openai_compatible",
  "base_url": "https://spark-api-open.xf-yun.com/v1",
  "api_key": "example-key",
  "chat_model": "lite"
}
```

响应同 `GET /settings/model`，不返回明文 API Key。

### POST `/settings/model/test`

用途：测试模型连通性。Phase 6.2 后该接口作为兼容接口保留，测试当前用户默认配置；没有默认配置时测试服务器兜底配置。后端发送极短 Chat Completions 测试请求，成功或失败都只返回摘要，不记录完整 Key、完整 prompt 或上传资料原文。

响应：

```json
{
  "data": {
    "ok": true,
    "source": "user",
    "chat_model": "gpt-4.1-mini",
    "message": "模型连接成功。",
    "config_id": 1
  },
  "trace_id": "trace_settings_002"
}
```

### GET `/settings/model/configs`

用途：读取当前用户所有模型配置和服务器兜底摘要。Phase 6.2 已实现，必须携带 JWT。每条用户配置互相隔离，Key 只返回脱敏值。

响应：

```json
{
  "data": {
    "configs": [
      {
        "id": 1,
        "source": "user",
        "display_name": "星火 Lite",
        "preset_id": "spark",
        "provider": "openai_compatible",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "chat_model": "lite",
        "embedding_model": null,
        "has_api_key": true,
        "api_key_masked": "sp-u...oken",
        "can_use_model": true,
        "is_default": true,
        "last_test_ok": true,
        "last_test_message": "模型连接成功。",
        "last_tested_at": "2026-07-04T10:00:00Z"
      }
    ],
    "system_summary": {
      "source": "system",
      "provider": "openai_compatible",
      "base_url": "https://api.example.com/v1",
      "chat_model": "example-chat-model",
      "embedding_model": null,
      "has_api_key": false,
      "api_key_masked": null,
      "can_use_model": false
    },
    "default_config_id": 1
  },
  "trace_id": "trace_settings_configs"
}
```

### POST `/settings/model/configs`

用途：创建当前用户的一条模型配置。`display_name` 在同一用户内不能重复；`make_default=true` 时会取消该用户其他默认项。第一条个人配置会自动成为默认配置。

请求：

```json
{
  "display_name": "星火 Lite",
  "preset_id": "spark",
  "provider": "openai_compatible",
  "base_url": "https://spark-api-open.xf-yun.com/v1",
  "api_key": "example-key",
  "chat_model": "lite",
  "embedding_model": null,
  "make_default": true
}
```

响应：返回单条配置摘要，不返回明文 API Key。

### PATCH `/settings/model/configs/{config_id}`

用途：更新当前用户自己的模型配置。只允许访问当前用户的配置；跨用户配置返回 404。`api_key` 为空字符串或缺省时保留原密钥。

### POST `/settings/model/configs/{config_id}/default`

用途：把当前用户自己的某条配置设为默认，并取消同用户其他默认项。课程 RAG 回答运行时优先使用这条默认配置；默认不存在时才回退服务器 `.env` 配置。

### POST `/settings/model/configs/{config_id}/test`

用途：测试指定模型配置，并把脱敏测试状态写入 `last_test_ok`、`last_test_message`、`last_tested_at`。测试失败也不记录明文 Key、完整 prompt 或课程资料原文。

### DELETE `/settings/model/configs/{config_id}`

用途：删除当前用户自己的某条模型配置。删除默认配置后，后端会把剩余配置中最近更新的一条设为默认；没有个人配置时回退服务器配置。

模型 Provider 第一版按 OpenAI-compatible 协议实现：

- 聊天回答：`{base_url}/chat/completions`。
- 向量生成：`{base_url}/embeddings`。
- 课程回答运行时优先使用当前用户默认配置。
- 用户没有默认配置时回退服务器 `.env` 兜底配置。

Phase 6.2 后设置页可见预设收敛为：

- 讯飞星火 Spark。
- DeepSeek。
- 通义千问。
- Kimi。
- 智谱 GLM。
- 百度千帆。
- 腾讯混元。
- 硅基流动。
- 本地 Ollama。
- 本地 LM Studio。
- 自定义兼容服务。

OpenRouter 不再作为可见预设。

讯飞星火 Spark 推荐配置：

- Base URL：`https://spark-api-open.xf-yun.com/v1`。
- 默认聊天模型：`lite`。
- 可选聊天模型：`lite`、`generalv3`、`pro-128k`、`max-32k`、`4.0Ultra`。

讯飞原生 Embeddingp/Embeddingq 因为独立授权、签名鉴权和 2560 维输出，当前阶段不接入。

## 20. API 验收标准

第一版接口达到以下标准才算可进入前端联调：

1. 认证接口稳定。
2. 所有学生数据接口校验当前用户。
3. 上传资料接口能返回进度。
4. RAG 和 AI 输出接口包含引用字段。
5. 多智能体任务包含 trace_id。
6. 错误响应结构统一。
7. API Key 不以明文返回或写入日志。
8. Demo 接口能重置演示数据。
