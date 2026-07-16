# EduNova API 设计

日期：2026-07-01

## 1. 设计目标

本文档定义 EduNova 第一版前后端接口约定。接口设计以学生学习主链路为中心，兼顾隔离示例课程、RAG 引用、多智能体轨迹和后续开源部署。

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
agents
resources
paths
practice
reports
exports
```

当前前端仍保留以下合同常量，方便后续 Phase 接入，但它们不是当前已经挂载的后端 router，不能在页面或文档中当作已实现接口：

```text
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
  "account": "student_01",
  "password": "Password123",
  "display_name": "小新",
  "starter_mode": "data_structures"
}
```

`starter_mode` 用于决定新账号首次进入学习空间时是否安装内置课程：

- `blank`：空白开始，不自动创建内置课程、资料或主页历史。
- `data_structures`：安装“数据结构与算法”课程、课程内部来源、56 个知识点和 184 个知识切片。

如果前端没有传入，后端默认按 `blank` 处理。内置课程来源只保存在 `course_materials`，不会创建个人资料库 `materials`，也不能复用其他用户资料。

注册接口只返回用户对象，不直接返回 token。前端注册成功后再调用登录接口写入本地 session；如果自动登录失败，跳回登录页提示用户重新登录。

响应：

```json
{
  "data": {
    "id": 1,
    "account": "student_01",
    "display_name": "小新",
    "role": "student",
    "starter_mode": "data_structures"
  },
  "trace_id": "trace_20260701_001"
}
```

### POST `/auth/login`

用途：登录。

请求：

```json
{
  "account": "student_01",
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
      "account": "student_01",
      "display_name": "小新",
      "role": "student",
      "starter_mode": "data_structures"
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
    "account": "student_01",
    "display_name": "小新",
    "role": "student",
    "starter_mode": "data_structures"
  },
  "trace_id": "trace_20260701_003"
}
```

### PATCH `/auth/me`

用途：更新当前学生账号的基础资料。当前只允许修改昵称，不修改登录账号、密码、角色或 starter mode。更新后前端会刷新本地登录态和侧栏昵称。

请求：

```json
{
  "display_name": "小新"
}
```

响应：

```json
{
  "data": {
    "id": 1,
    "account": "student_01",
    "display_name": "小新",
    "role": "student",
    "starter_mode": "data_structures"
  },
  "trace_id": "trace_20260707_001"
}
```

错误：

- HTTP 422：昵称为空或超过长度限制。
- `401 UNAUTHORIZED`：未登录或 token 失效。

### PATCH `/auth/me/password`

用途：修改当前账号密码。必须验证当前密码；新密码至少 8 位并同时包含字母和数字，且不能与当前密码相同。成功后用户的 `auth_version` 递增，当前令牌和其他设备上的旧 JWT 均立即失效，客户端需要使用新密码重新登录。无 `auth_version` 声明的历史令牌按版本 `0` 兼容。

请求：

```json
{
  "current_password": "Password123",
  "new_password": "NewPassword456"
}
```

成功响应：

```json
{
  "data": { "ok": true },
  "trace_id": "trace_password_001"
}
```

当前密码错误返回 `400 INVALID_CURRENT_PASSWORD`；弱密码或与当前密码相同返回 `422 VALIDATION_ERROR`。接口不返回密码摘要，也不在日志中记录密码原文。

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
- `data_structures` 注册用户返回复制到该用户空间的数据结构与算法课程；资料摘要仍只统计用户上传原文件。
- 课程进度只显示真实进度；没有进度记录时显示“未开始”，不使用前端写死的演示百分比。
- 本接口不创建会话、不上传资料、不触发 AI/RAG，也不生成课程。

响应示例：

```json
{
  "data": {
    "profile_summary": {
      "display_name": "小新",
      "starter_mode": "data_structures",
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
        "title": "数据结构与算法",
        "source_type": "builtin",
        "progress_label": "未开始",
        "focus": "计算机科学",
        "next": "开始学习"
      }
    ],
    "material_library_summary": {
      "material_count": 0,
      "unassigned_count": 0
    },
    "recent_materials": [],
    "recent_resources": [],
    "command_suggestions": [
      "继续学习《数据结构与算法》",
      "帮我复习《数据结构与算法》的薄弱点",
      "先帮我拆解下一步复习计划"
    ],
    "evidence_summary": {
      "citation_count": 0,
      "latest_trace_id": null,
      "low_evidence_count": 0
    },
    "empty_state": {
      "kind": "starter",
      "title": "从数据结构与算法开始",
      "description": "内置课程已经进入你的学习空间，可以直接阅读课程内容或开始提问。",
      "action_label": "开始学习"
    }
  },
  "trace_id": "trace_20260701_004"
}
```

## 6. Profile 接口

状态：Phase 15 已由 `ProfileGraph` 接管。显式画像回答经过结构化抽取与审核后更新；不确定表达保留为候选证据。课程问答和练习产生的隐式信号使用独立 Graph trace，相同归一化结论至少来自 2 个独立来源且提案聚合置信度不低于 0.60 时才能形成已应用判断；其逐维证据分数仍需达到 70% 才能直接参与下游个性化。

### GET `/profiles/me`

用途：读取当前学生画像。

规则：

- 必须携带 JWT，只读取当前用户自己的画像。
- 空画像也返回稳定 8 维结构，字符串字段为空字符串，`weak_points=[]`。
- `version` 由当前画像关联的画像事件数量派生。
- `next_question` 用于前端画像对话入口，不等同于强制问卷；优先追问本轮提及但未识别的维度，其次选择缺失或可信度最低的维度。
- `next_question_dimension` 向后兼容标识该问题对应的八维字段，前端据此展示友好维度名、回答范围和不可点击的纯文本例子；旧客户端可忽略，旧响应缺少时前端使用通用引导。
- `profile_json` 是用户级画像。`knowledge_foundation`、`weak_points`、`learning_goal` 可以在后续展示和推荐中叠加课程级状态，但 `/profiles/me` 不返回每门课程一份画像。
- `completeness_score` 按八个非空维度等权计算；薄弱点空数组视为空。它只表示画像填写完整程度。
- `evidence_confidence_score` 只平均已有维度的证据分数；兼容字段 `confidence_score` 与其保持一致，不再充当完整度。
- `applied_version` 是已应用画像事件版本；候选事件不增加该版本。
- `dimension_confidence` 返回各维度 0-100 证据分数，`dimension_evidence_summary` 返回可信等级、独立来源数和最近来源；`evidence_summary` 返回候选/已应用证据计数。

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
    "completeness_score": 100,
    "evidence_confidence_score": 72,
    "applied_version": 3,
    "dimension_confidence": {"major_background": 82, "learning_goal": 76},
    "dimension_evidence_summary": {
      "learning_goal": {"confidence": 76, "level": "trusted", "source_count": 2}
    },
    "evidence_summary": {"candidate_count": 1, "applied_count": 3},
    "updated_reason": "更新学习画像：学习目标、知识基础",
    "updated_at": "2026-07-05T09:00:00Z",
    "next_question": "这门课你最担心哪一章？",
    "next_question_dimension": "weak_points"
  },
  "trace_id": "trace_profile_me"
}
```

### POST `/profiles/chat`

用途：通过 `ProfileGraph` 对话更新学习画像。模型负责理解自然语言并生成现有 8 个白名单字段，不要求结果先命中人工关键词；只有有效模型提案可以更新画像，规则只负责字段、类型、长度、去重、敏感内容和可信度校验，不补写模型遗漏。模型输出支持纯 JSON、JSON 代码块和正文中的完整 JSON 对象；首次结构无效时只修复一次，仍不可用、低置信或审核拒绝时不改变长期画像。职业愿景、兴趣方向和社会贡献可以由模型提案为 `motivation_interest`，明确能力目标可以提案为 `learning_goal`。

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
      "status": "applied",
      "source_type": "profile_chat",
      "confidence_score": 0.70,
      "agent_trace_id": "trace_profile_graph",
      "change_summary": "更新学习画像：学习目标、薄弱点",
      "evidence_json": {
        "source_type": "profile_chat",
        "updated_dimensions": ["learning_goal", "weak_points"],
        "candidate_dimensions": [],
        "generation_mode": "model_enhanced",
        "parse_status": "valid",
        "repair_count": 0,
        "review_mode": "model_and_rules",
        "dimension_evidence_scores": {"learning_goal": 0.78, "weak_points": 0.70},
        "source_factor": 1.0,
        "review_factor": 1.0
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
- 显式画像事件的 `evidence_json` 可增加 `generation_mode=model_enhanced|rules_only`、`parse_status`、`repair_count` 和 `review_mode`；这些字段只描述安全执行方式，不保存模型原始回答或用户完整输入。
- 画像事件是证据流。带 `course_id` 的事件可以作为课程学习状态的候选来源，但不能直接视为已确认弱点或复习队列项。
- 后续可增加 `course_id` 查询参数过滤某门课相关证据；当前实现仍返回当前用户最近画像事件。

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

用途：获取课程概览、章节和知识点。Phase 15 新课程可选返回 `structure` v2，包括学习目标、章节知识点 ID、补充来源、生成/审核模式和来源覆盖摘要；旧课程返回空结构。

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
  "difficulty": "基础",
  "prerequisite_ids": ["9000"]
}
```

### GET `/courses/{course_id}/mastery-map`

### GET `/courses/{course_id}/knowledge-points/{knowledge_point_id}/content`

用途：读取当前用户课程中某个知识点的真实学习内容。接口聚合已落库的课程切片、资料来源、页码、相关资源和前后知识点导航，不调用模型动态生成课文。

响应 `data` 包含 `knowledge_point`、`sections`、`related_resources`、`previous_knowledge_point_id` 和 `next_knowledge_point_id`。`sections` 每项返回 `chunk_id`、`title`、`content`、`source_title` 和可选 `page_number`。

规则：只能访问当前用户自己的课程和知识点；最多返回 12 个切片，单个正文不超过 1200 字。不返回向量、存储路径、原始 metadata、完整资料文件或模型输入。

### GET `/courses/{course_id}/mastery-map`

状态：Phase 9 已实现。

用途：获取课程级证据掌握度图。掌握度不单独持久化，按已完成练习中的有效作答、当前课程弱点及明确完成的学习证据实时计算；路径任务和资源存在性不再直接产生分数。

规则：

- 必须携带 JWT，只允许访问当前用户自己的课程。
- `confirmed/reviewing` 弱点映射为 `weak`。
- Phase 10 后，练习作答低分或错误的知识点映射为 `weak`，正确或高分知识点可提升为 `mastered`。
- 已完成弱点到达 `next_review_at` 时映射为 `recommended_review`。
- 完成练习中的真实作答按客观得分形成证据；零分必须保留为零分。
- 没有有效证据的知识点返回 `status=not_started`、`score=null`，不参与课程平均掌握度。
- 路径任务只表达学习顺序和完成进度，不改变掌握度。
- 响应不包含完整用户问题、系统提示词、模型输入、API Key、完整课程资料原文或完整画像原文。

响应：

```json
{
  "data": {
    "course_id": "101",
    "summary": {
      "total_count": 3,
      "weak_count": 1,
      "learning_count": 1,
      "mastered_count": 1,
      "recommended_review_count": 0,
      "not_started_count": 0,
      "assessed_count": 3,
      "unassessed_count": 0,
      "average_score": 58
    },
    "points": [
      {
        "id": "9001",
        "title": "启发式搜索",
        "chapter": "搜索问题",
        "order_index": 1,
        "status": "weak",
        "score": 35,
        "evidence_count": 2,
        "confidence": 0.78,
        "last_assessed_at": "2026-07-14T08:00:00Z",
        "prerequisite_ids": [],
        "weakness_item_ids": ["7001"],
        "recommended_resource_ids": ["8001"]
      }
    ]
  },
  "trace_id": "trace_mastery_map"
}
```

### GET `/courses/{course_id}/learning-state`

状态：Phase 10 已更新。Phase 7.3 完成课程问答候选事件入队，Phase 7.4 增加队列项确认、开始、完成和忽略操作，Phase 9 增加推荐资源、下次复习时间、真实路径摘要和掌握度摘要，Phase 10 接入练习评估对弱点队列和掌握度的反哺。

用途：聚合某一门课程下的学习状态，并把课程问答产生的弱点候选画像事件确定性同步为待确认复习项。当前会返回弱点队列、路径摘要和规则掌握度摘要；练习提交后，低分或错误题对应的 `practice_assessment` 弱点会以 `confirmed` 来源进入队列并影响掌握度摘要。

规则：

- 必须携带 JWT，只允许访问当前用户自己的课程。
- 读取用户级 `student_profiles` 作为长期偏好和背景，不复制完整画像。
- 请求时执行一次确定性同步：只处理当前课程下 `dimension="weak_points"`、`evidence_json.source_type="course_question"` 的画像候选事件。
- 有 `knowledge_point_id` 时按知识点去重；无知识点时按安全标题去重，标题优先使用 `section_title`、`source_title`，否则使用“课程问答薄弱点”。
- 新入队项写入 `weakness_review_queue`，状态为 `pending`，产品语义是“待确认/待复习”，不是系统已经完成正式诊断。
- 已存在同课程同知识点或同标题的 `pending/confirmed/reviewing/completed/dismissed` 项时不重复创建，避免已忽略项被候选事件重新入队。
- `weakness_review_queue` 主列表只返回非 `dismissed` 项；`dismissed` 仍参与统计和去重。
- `confirmed/reviewing/completed` 复习项会按同课程同知识点资源或安全标题匹配补充 `recommended_resource_ids` 和资源摘要；`pending` 仍只表示待确认，不直接作为路径依据。
- `confirmed/reviewing` 项若缺少 `next_review_at`，读取学习状态时可确定性补齐；`complete` 操作会设置下一次复习时间。
- `path_summary` 读取同课程最新 `active` 学习路径，不存在时返回真实空摘要。
- `mastery_summary` 复用掌握度图规则实时统计，并纳入 Phase 10 练习结果。
- 队列和响应不包含完整用户问题、系统提示词、模型输入或资料原文。

响应字段：

- `course_id`。
- `profile_overlay`：兼容字段，由当前课程上下文派生；目标优先取当前路径目标，基础叠加本课程掌握度摘要，弱点只返回当前课程弱点。
- `learner_context`：实时派生的课程学习上下文，包含画像应用版本、可信/弱提示维度数量、画像完整度、课程目标、掌握度、当前任务、课程弱点、最近练习、资源类型、报告状态和脱敏 `context_hash`。不复制完整用户画像，也不持久化课程画像表。
- `weakness_summary`：`candidate_event_count`、`pending_count`、`confirmed_count`、`reviewing_count`、`completed_count`、`dismissed_count`、`latest_evidence_at`。
- `weakness_review_queue`：复习项数组，包含 `id`、`title`、`status`、`source_type`、`course_id`、`knowledge_point_id`、`recommended_resource_ids`、`recommended_resources`、`next_review_at`、`created_at`、`updated_at`。
- `path_summary`：`status`、`message`、`path_id`、`current_task_title`、`task_count`、`completed_task_count`。
- `mastery_summary`：`total_count`、`weak_count`、`learning_count`、`mastered_count`、`recommended_review_count`、`not_started_count`。
- `evidence_summary`：候选事件数量、最新 `trace_id` 和最新安全来源标题/章节摘要。

错误：

- 未登录返回 401。
- 课程不存在或不属于当前用户返回 404。

## 8. Materials 接口

### POST `/materials/upload`

用途：上传资料到当前登录用户的个人资料库。Phase 21 起支持深度解析的文件会创建 `material_ingestion` 后台任务；上传响应只表示原文件已安全入库，不表示目录和切片已经确认。

请求类型：`multipart/form-data`

字段：

- `course_id`：可选。传入时表示上传后同时加入该课程；不传时仅进入个人资料库。
- `file`：上传文件。

支持类型：

- TXT、Markdown、PDF、DOCX、PPTX：原文件入库后创建 `MaterialIngestionGraph` 任务，成功后进入 `awaiting_confirmation`，用户确认目录后进入 `confirmed`。
- DOC、PPT：旧版 Office 格式仅入库为 `uploaded`，提示旧版格式暂不支持深度解析。
- PNG、JPG、JPEG、WEBP：仅入库为 `uploaded`，提示“仅入库，暂不做 OCR”。
- 损坏或无法读取的 PDF/DOCX/PPTX 标记为 `failed`，错误信息只返回脱敏提示，不暴露底层异常或文件路径。

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
    "parse_status": "uploaded",
    "ingestion_job_id": "job_20260714_001",
    "ingestion_status": "pending"
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
    "extracted_text_preview": "第一章 数据结构与算法基础...",
    "chunk_count": 8,
    "section_count": 3,
    "page_count": 6,
    "sections": [
      {
        "section_title": "监督学习",
        "page_number": 2,
        "chunk_count": 3,
        "preview": "监督学习使用标注样本建立输入与输出的关系。"
      }
    ],
    "linked_courses": [
      {
        "id": "12",
        "title": "机器学习复习",
        "usage_type": "reference"
      }
    ],
    "agent_trace_id": "trace_material_1"
  },
  "trace_id": "trace_20260701_007"
}
```

详情只返回当前用户可见的安全摘要，并增加 `ingestion_status`、`parser_version`、`outline_version`、`quality_summary` 与 `parsed_at`。`sections` 最多返回 20 个章节，每个预览不超过 180 字；完整目录和切片检查通过下方 outline 接口读取。接口不返回存储路径、向量、原始 metadata 或模型输入。

### GET `/materials`

用途：查看当前用户个人资料库。Phase 4.4 已实现，支持筛选未归属课程资料、某课程已关联资料和最近上传资料。`/app/library` 和主页资料库浮层都通过该接口读取完整资料列表；`/dashboard/summary.recent_materials` 只承担主页摘要。

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

用途：查看资料解析进度。Phase 21 返回资料入库、后台解析、待确认、已确认或失败状态；建课进度继续由独立 AI Job 查询。

响应：

```json
{
  "data": {
    "status": "completed",
    "progress_percent": 100,
    "message": "解析完成，等待确认目录"
  },
  "trace_id": "trace_20260701_010"
}
```

### POST `/materials/{material_id}/ingestion-jobs`

用途：为当前用户自己的资料创建重新解析或重试任务。成功返回 HTTP 202 和现有 `AiJobResponse`，`workflow=material_ingestion`。运行中的同一资料任务由幂等键复用；任务支持取消、失败重试和刷新恢复。

只有 TXT、Markdown、PDF、DOCX 和 PPTX 可进入深度解析。旧版 DOC/PPT、图片和扫描件不会伪装为可解析资料。

### GET `/materials/{material_id}/outline`

用途：读取当前资料的目录版本、章节树、章节到切片映射和安全质量报告。响应中的切片正文只用于当前用户检查自己的资料，带有章节路径、起止页、类型、内容哈希和质量提示；不返回向量、存储路径或模型原始输出。

主要字段：

```json
{
  "material_id": 1,
  "version": 3,
  "status": "awaiting_confirmation",
  "confirmed": false,
  "quality": {
    "status": "passed",
    "readable_page_ratio": 0.98,
    "duplicate_chunk_ratio": 0.02,
    "warnings": []
  },
  "sections": [],
  "chunks": []
}
```

### PATCH `/materials/{material_id}/outline`

用途：按目录版本执行结构编辑。请求必须携带当前 `version`，支持 `rename`、`include`、`exclude`、`merge` 和 `split`；版本不一致返回 409，防止覆盖其他已保存编辑。成功后目录版本递增，资料重新进入待确认状态。

### POST `/materials/{material_id}/outline/confirm`

用途：确认当前目录版本。只有解析质量通过、至少包含一个有效章节且切片满足页码和章节边界要求时才可确认。确认后资料进入 `confirmed`，主页资料问答、资料对比和智能建课才会读取该结构。

### POST `/courses/from-materials`

用途：根据资料库中的一个或多个资料生成课程。Phase 21 的 `CourseBuilderGraph` 只接受当前用户已确认且解析质量通过的 TXT、Markdown、PDF、DOCX 和 PPTX。待确认资料返回 409；解析失败、legacy、旧版 Office、图片或扫描件不会进入建课。

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
      "compared_material_count": 2,
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

- 用户填写课程名时始终优先使用；未填写才使用模型建议或文件名 fallback。
- Graph 节点为 `validate_confirmed_materials -> coherence_gate -> load_outlines -> chapter_plan -> concept_workers -> aggregate -> prerequisite_graph -> evidence_bind -> review -> repair -> persist`。
- `concept_workers` 使用 LangGraph `Send` 按章节并行，每个 Worker 只读取本章节真实切片；知识点数量根据章节与正文规模自适应，硬上限 120。
- 多资料先执行主题一致性门禁。规则审核章节覆盖、主体切片覆盖率、知识点密度、重复标题、真实引用、先修环路、难度和隐私边界，最多修订一次。
- 每个知识点至少绑定一个真实切片，所有纳入课程的章节都有知识点覆盖，主体切片覆盖率至少 85%；未通过门禁时课程零落库。
- 后端会创建 `Course`、`CourseEnrollment`、兼容旧链路的 `CourseMaterial`、`CourseMaterialLink`、`KnowledgePoint` 和 `KnowledgeChunk`。
- 课程生成会 best-effort 为新 `KnowledgeChunk` 写入当前默认配置的真实外部 embedding；实际维度与配置指纹一并保存，失败只记录 warning 并回退关键词检索。
- `knowledge_chunks.metadata_json` 会记录 `embedding_source`、`embedding_model`、`embedding_dimension`、`embedded_at`，便于识别基础检索状态、过期模型和后续重建。
- 前端 `/app` 主页资料库浮层和 `/app/library` 使用同一接口；成功后刷新 summary/materials 并跳转 `/app/courses/{course_id}`。
- Phase 17 起当前前端改用 `POST /courses/from-materials/jobs`；本同步接口保留给旧客户端和内部兼容调用。

### POST `/materials/compare`

用途：由 `MaterialComparisonGraph` 对同一课程下 2 份以上资料做可追溯对比，输出重复重点、疑似考点、单资料独有点、试题独有点、遗漏复习点、优先复习顺序和安全引用。每次调用创建不可变版本；规则结果完整可用，模型只增强解释和复习排序。

请求：

```json
{
  "course_id": 1,
  "material_ids": [1, 2, 3]
}
```

请求规则：

- 必须携带 JWT。
- `course_id` 必须属于当前用户。
- `material_ids` 使用资料库 `materials.id`，去重后至少 2 份。
- 每个资料必须属于当前用户，并且已通过 `course_material_links` 绑定到当前课程。
- 少于 2 份可比较资料返回 400；非本人课程、非本人资料或未绑定当前课程资料返回 404。
- 优先读取 `knowledge_chunks.metadata_json.source_material_id` 和 `course_materials.metadata_json.source_material_id` 做课程切片对比；若没有切片且资料已解析完成，则只使用 `Material.extracted_text` 的安全短摘录 fallback。

响应：

```json
{
  "data": {
    "id": "1201",
    "course_id": "1",
    "material_ids": ["1", "2"],
    "summary": {
      "material_count": 2,
      "comparable_material_count": 2,
      "matched_concept_count": 5,
      "citation_count": 4,
      "message": "已基于课程知识切片和安全短摘录完成资料对比。"
    },
    "repeated_concepts": [
      {
        "title": "启发式搜索",
        "material_ids": ["1", "2"],
        "source_titles": ["数据结构讲义.md", "期末样题.md"],
        "reason": "多份资料重复出现。",
        "confidence": "high",
        "support_count": 2,
        "knowledge_point_id": "10"
      }
    ],
    "exam_likely_points": [],
    "materials_only_points": [],
    "questions_only_points": [],
    "missing_review_points": [],
    "priority_order": [],
    "citations": [
      {
        "material_id": "1",
        "source_title": "数据结构讲义.md",
        "section_title": "启发式搜索",
        "page_number": null,
        "excerpt": "启发式搜索使用启发函数估计路径代价。",
        "confidence": "high"
      }
    ],
    "generation_mode": "deterministic_source",
    "review_mode": "rules_only",
    "review_result": {
      "review_status": "passed",
      "confidence": 0.82,
      "risk_flags": [],
      "safety_summary": "引用和资料范围校验通过。"
    },
    "warnings": [],
    "created_at": "2026-07-11T10:00:00Z"
  },
  "trace_id": "trace_20260705_001"
}
```

隐私边界：

- `citations.excerpt` 只返回短摘录。
- 响应不包含完整资料原文、系统提示词、模型输入、API Key 或用户隐私原文。
- 审核后的安全结果写入 `material_comparison_runs`；重新对比会创建新版本，不覆盖历史结果。
- 低重合时返回 warning，不伪造共同重点；模型不得创建不存在的资料、知识点或引用 ID。

### GET `/materials/comparisons/latest?course_id=...`

用途：恢复当前用户当前课程最近一次资料对比；没有结果时返回 `data=null`。

### GET `/materials/comparisons/{comparison_id}`

用途：读取当前用户自己的不可变资料对比版本。非本人记录或课程不匹配返回 404。

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
        "source_title": "数据结构讲义",
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
- 后端优先使用当前用户向量默认配置。讯飞使用原生签名接口和 2560 维 `query/para`；百炼、硅基及自定义服务使用 OpenAI-compatible `/embeddings`，实际维度由预设或连接测试识别。向量默认与回答默认可以来自不同配置。
- 如果没有可用 embedding 模型或 Provider 调用失败，后端使用关键词 fallback；旧 1536 维数据缺少当前配置指纹时视为 legacy，不进入当前向量候选。
- 外部 embedding 失败时不阻断问答，接口会退回关键词检索并通过 `embedding_status` 暴露状态。
- 关键词 Top 30 与向量 Top 30 使用 RRF 合并为 Top 20；配置重排序后返回 Top 5。重排序失败只退回 RRF，不跨 Provider 自动转发。

## 10. Resource 接口

状态：已完成六类结构化资源和多模态呈现。当前只生成课程资源：`course_id != null` 表示课程资源；`course_id == null` 仅预留个人全局资源语义。

统一规则：

- 所有接口必须携带 JWT。
- 只能生成和读取当前用户自己的课程、知识点、资源和质量分；非本人资源或课程返回 404。
- `resource_type` 支持 `doc`、`mindmap`、`quiz`、`code`、`slide`、`animation`。
- `ResourceGenerationGraph` 使用 LangGraph `Send` 为每个请求类型并行派发独立 Worker。每个 Worker 直接生成 v3 类型化 artifact；ReviewAgent 读取安全资料摘录、学习目标和完整候选内容，失败资源最多执行一次结构修复和一次内容修订。
- `planner` 为每个 Worker 生成结构化 `ArtifactIntent`，包含教学策略、认知层级、案例方向、资源职责、真实证据和可验证学习结果。可信画像不足时必须标记 `context_limited`。
- 资源按 `version_family_id + version_number` 形成不可覆盖的版本族。`alternative` 必须相对来源版本至少改变教学策略、案例、认知层级、交互结构中的两项；`refine` 必须保持原教学意图。`content_json.diversity` 始终记录本地文字与结构差异；配置可用向量模型时还会记录 `semantic_similarity/semantic_status`，向量服务不可用时安全降级且不伪造语义校验结果。
- `content_json.schema_version=3` 必须包含 `format=rich`、`artifact.kind`、Markdown fallback、引用绑定、`quality` 和 Prompt 版本。`generation_mode=model_enhanced` 仅在模型结果相对底稿存在有效差异并通过门禁时使用。
- 讲解、导图和 PPT 可保存通过规则门禁的证据型降级稿；练习、代码和动画不合格时进入 `failed_resource_types` 且不持久化。代码还必须通过内部 Pyodide 运行验证，验证服务不可用时不得保存未经运行的代码。
- 响应、资源内容、质量分和 Agent trace 只保存安全摘要、引用标题和白名单 metadata，不返回系统提示词、完整模型输入、API Key、完整课程资料原文或完整用户画像原文。

### POST `/resources/generate`

用途：为当前用户的一门课程同步生成 1 到 6 类学习资源。

Phase 17 起课程空间和资源工坊改用 `POST /resources/generation-jobs`；本同步接口不删除、不改响应字段。

请求：

```json
{
  "course_id": 1,
  "knowledge_point_id": 8,
  "resource_types": ["doc", "mindmap", "quiz", "code", "slide", "animation"],
  "learning_goal": "理解反向传播",
  "difficulty": "medium",
  "generation_action": "new",
  "source_resource_id": null
}
```

字段规则：

- `course_id` 必填。
- `knowledge_point_id` 可选；填写时必须属于该课程。
- `resource_types` 必须为 1 到 6 个，服务端会去重。
- `learning_goal` 可选，最长 500 字，只用于本次生成，不作为完整用户资料保存到日志。
- `difficulty` 默认为 `medium`，可选 `easy`、`medium`、`hard`。
- `generation_action` 默认为 `new`，可选 `new`、`alternative`、`refine`。
- `source_resource_id` 在 `alternative/refine` 时必填，在 `new` 时必须为空；来源资源必须属于当前用户、当前课程且与请求资源类型一致。

响应：

```json
{
  "data": {
    "agent_trace_id": "trace_20260705_resource_001",
    "resources": [
      {
        "id": "1",
        "course_id": "1",
        "knowledge_point_id": "8",
        "resource_type": "doc",
        "title": "反向传播个性化讲解",
        "content_json": {
          "schema_version": 3,
          "format": "rich",
          "markdown": "# 反向传播个性化讲解\n\n先理解链式法则，再看计算图中的梯度传递。",
          "artifact": {
            "kind": "document",
            "sections": [
              {"heading": "概念解释", "body": "反向传播通过计算图逐层传递梯度。"}
            ],
            "citation_refs": [501]
          },
          "metadata": {
            "agent_trace_id": "trace_20260705_resource_001",
            "generation_mode": "model_enhanced",
            "review_mode": "model_and_rules",
            "prompt_version": "resource-doc-v3",
            "repair_count": 0,
            "difficulty": "medium",
            "has_learning_goal": true,
            "source_excerpt_count": 3,
            "model_enhancement_failed": false
          },
          "quality": {
            "status": "passed",
            "source_coverage": 1.0,
            "dimensions": {
              "authenticity": {"status": "passed", "score": 1.0},
              "personalization": {"status": "passed", "score": 0.86},
              "diversity": {"status": "passed", "score": 0.91},
              "pedagogical_utility": {"status": "passed", "score": 0.88},
              "type_correctness": {"status": "passed", "score": 1.0}
            },
            "code_verification": null
          },
          "intent": {
            "teaching_strategy": "derivation_first",
            "cognitive_level": "analyze",
            "resource_role": "解释核心概念、依据与推导过程",
            "evidence_refs": [501],
            "generation_action": "new"
          },
          "personalization_summary": {
            "status": "personalized",
            "learning_problem": "优先解决梯度推导困难",
            "teaching_reason": "结合当前薄弱点采用逐步推导",
            "difference": "本资源专注概念解释与推导"
          }
        },
        "citation_json": [
          {
            "chunk_id": 501,
            "knowledge_point_id": 8,
            "source_title": "神经网络讲义.md",
            "section_title": "反向传播",
            "page_number": null
          }
        ],
        "status": "completed",
        "review_status": "passed",
        "confidence_score": 0.82,
        "agent_trace_id": "trace_20260705_resource_001",
        "version_family_id": "7cb08790-2d5f-4f5c-a10d-d13d42fe3eb4",
        "revision_of_resource_id": null,
        "version_number": 1,
        "generation_action": "new",
        "created_at": "2026-07-05T14:00:00Z",
        "updated_at": "2026-07-05T14:00:00Z"
      }
    ],
    "quality_scores": {
      "1": [
        {
          "id": "3001",
          "resource_id": "1",
          "score_name": "source_match",
          "score_value": 0.82,
          "rationale": "基于课程引用摘要生成。",
          "created_at": "2026-07-05T14:00:00Z"
        }
      ]
    },
    "warnings": [],
    "failed_resource_types": []
  },
  "trace_id": "trace_20260701_009"
}
```

### GET `/resources`

用途：获取当前用户资源列表。可通过 `course_id` 和 `resource_type` 过滤；不传 `course_id` 时返回当前用户全部资源，包含后续可能出现的个人全局资源。

查询参数：

- `course_id`：可选，限制为某门课程资源。
- `resource_type`：可选，限制为 `doc`、`mindmap`、`quiz`、`code`、`slide` 或 `animation`。

响应为分页列表 envelope：

```json
{
  "data": [
    {
      "id": "1",
      "course_id": "1",
      "knowledge_point_id": "8",
      "resource_type": "quiz",
      "title": "反向传播练习",
      "content_json": {
        "markdown": "# 反向传播练习",
        "metadata": {
          "agent_trace_id": "trace_20260705_resource_001",
          "generation_mode": "deterministic_source",
          "source_excerpt_count": 2,
          "model_enhancement_failed": true
        }
      },
      "citation_json": [],
      "status": "completed",
      "review_status": "passed",
      "confidence_score": 0.78,
      "agent_trace_id": "trace_20260705_resource_001",
      "created_at": "2026-07-05T14:00:00Z",
      "updated_at": "2026-07-05T14:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 1,
  "total": 1,
  "trace_id": "trace_20260705_011"
}
```

### GET `/resources/{resource_id}`

用途：获取当前用户自己的资源详情。不存在或不属于当前用户时返回 404。

### GET `/resources/{resource_id}/quality`

用途：获取当前用户自己的资源质量评分。评分项包括旧的来源、画像、事实、难度和完整度，以及 Phase 20 新增的 `authenticity`、`personalization`、`diversity`、`pedagogical_utility` 和 `type_correctness`。

### POST `/resources/{resource_id}/exports`

用途：为当前用户自己的 `slide` 资源创建异步 PPTX 导出任务。请求为 `{"format":"pptx"}`；同一资源已有 queued、running 或 completed 的 PPTX 任务时复用该任务。非 PPT 资源返回 400，非本人资源返回 404。

### GET `/resources/{resource_id}/exports`

用途：列出当前用户指定资源的导出任务，按新到旧返回。任务继续通过 `GET /exports/{job_id}` 查询并通过 `/download` 下载。

## 11. Agent Trace 接口

状态：十条生产主链路已进入真实 LangGraph：资料精细解析、画像、资料建课、资料对比、主页问答、课程问答、资源生成、路径、练习评估和报告。学习档案导出继续使用普通 Service + RQ Worker。

### GET `/agents/traces/{trace_id}`

用途：获取当前用户自己的某次 Agent 任务轨迹。必须携带 JWT；trace 不存在或不属于当前用户时返回 404，避免跨用户枚举。

响应字段：

- `trace_id`：业务 trace。
- `workflow`：Graph 工作流，例如 `resource_generation`、`course_tutor`、`report`。
- `artifact_type`：产物类型，例如 `generated_resource`、`chat_message`、`assessment_report`。
- `artifact_id`：产物 ID，可能为空。
- `course_id`：关联课程，可能为空。
- `status`：由步骤状态派生，可能为 `running`、`completed`、`warning` 或 `failed`。
- `steps`：按 `step_index`、`created_at`、`id` 排序的步骤列表。
- `metadata`：仅返回白名单安全摘要，例如引用数量、审核结果、资源数量、`context_message_count`、`profile_applied_version`、可信维度数量、画像完整度、是否使用课程上下文和上下文版本；不返回系统提示词、模型输入、完整历史消息、完整资料原文、API Key 或用户画像原文。

响应：

```json
{
  "data": {
    "trace_id": "trace_20260705_agent_001",
    "workflow": "resource_generation",
    "artifact_type": "generated_resource",
    "artifact_id": "501",
    "course_id": "101",
    "status": "completed",
    "steps": [
      {
        "id": "1",
        "agent_name": "retrieve",
        "step_index": 1,
        "status": "completed",
        "input_summary": "检索课程知识点",
        "output_summary": "命中 2 条引用",
        "duration_ms": 25,
        "metadata": {
          "citation_count": 2,
          "context_message_count": 4,
          "context_summary_used": true,
          "retrieval_query_mode": "contextual",
          "review_status": "passed",
          "risk_flags": [],
          "workflow": "resource_generation"
        },
        "created_at": "2026-07-05T10:00:01Z"
      }
    ]
  },
  "trace_id": "trace_20260705_010"
}
```

## 12. Learning Path 接口

状态：Phase 9 已实现。当前后端已挂载 `paths` router，`/app/path` 读取真实课程路径、任务、推荐资源和掌握度图。

统一规则：

- 所有接口必须携带 JWT。
- 学习路径属于课程级能力，只允许访问当前用户自己的课程和任务。
- 生成或更新路径时归档同课程旧 `active` 路径为 `archived`，再写入新的 `learning_paths` 和 `learning_tasks`。
- 路径生成只消费 `confirmed/reviewing` 弱点队列、课程知识点、同课程生成资源和用户级画像叠层；`pending/dismissed` 不进入路径任务。
- 任务类型固定为 `review`、`learn`、`resource`，任务状态固定为 `todo`、`doing`、`completed`。
- `plan_json` 只保存安全摘要、生成规则、计数、依据说明和可展示 metadata，不保存系统提示词、模型输入、API Key、完整资料原文或完整画像原文。
- 路径响应可携带 `agent_trace_id`，用于前端展示 `PathPlanningGraph` 的轻量轨迹入口。

### POST `/paths/generation-jobs`

用途：异步创建当前用户某课程的路径规划任务。请求体继续为 `{"course_id": 1}`，必须携带 `Idempotency-Key`，成功返回 HTTP 202 与现有 `AiJobResponse`。同用户同课程已有 `queued/running/cancelling` 任务时返回该任务；刷新后通过 AI Job 列表或事件流恢复。结果包含 `course_id/path_id/generation_mode/preserved_task_count/warnings/trace_id`。失败或取消不覆盖原有效路径。

### POST `/paths/generate`（已废弃兼容）

用途：为旧客户端同步生成可执行学习路径。新版前端和项目内部流程不得调用。

请求：

```json
{
  "course_id": 1
}
```

- `course_id` 必填，必须是当前用户自己的课程。
- 学习目标优先读取用户画像；画像未提供目标时使用当前课程标题生成安全 fallback。
- 路径只返回有序任务、当前状态和推荐理由，不生成日期、期限或每日任务容量。

响应：

```json
{
  "data": {
    "course_id": "101",
    "status": "active",
    "message": "当前学习路径进行中。",
    "path": {
      "id": "901",
      "course_id": "101",
      "title": "机器学习 学习路径",
      "goal": "完成《机器学习》学习",
      "status": "active",
      "plan_json": {
        "schema_version": 5,
        "path_mode": "ordered",
        "strategy": "reviewing_first_then_confirmed_then_uncovered",
        "personalization": {"learning_preference": "图示优先"},
        "basis": ["课程知识点 6 个。", "已确认或复习中的薄弱点 2 个。"]
      },
      "created_at": "2026-07-05T16:00:00Z",
      "updated_at": "2026-07-05T16:00:00Z"
    },
    "tasks": [
      {
        "id": "1001",
        "path_id": "901",
        "course_id": "101",
        "knowledge_point_id": "9001",
        "title": "复习启发式搜索",
        "task_type": "review",
        "reason": "来自复习中的薄弱点。",
        "recommended_resource_ids": ["8001"],
        "recommended_resources": [
          {
            "id": "8001",
            "title": "启发式搜索讲解",
            "resource_type": "doc"
          }
        ],
        "learning_bundle": {
          "strategy": "先代码实验再概念复盘",
          "teaching_strategy": "先代码实验再概念复盘",
          "difficulty": "medium",
          "used_profile_factor_codes": ["major_background", "confirmed_weaknesses"],
          "generation_mode": "model_enhanced",
          "rationale": "先处理已确认薄弱点",
          "items": []
        },
        "status": "doing",
        "created_at": "2026-07-05T16:00:00Z",
        "updated_at": "2026-07-05T16:00:00Z"
      }
    ],
    "agent_trace_id": "trace_path_generate",
    "evidence_summary": {
      "knowledge_point_count": 6,
      "confirmed_or_reviewing_weakness_count": 2,
      "pending_weakness_count": 1,
      "resource_count": 3,
      "basis": ["课程知识点 6 个。"]
    }
  },
  "trace_id": "trace_path_generate"
}
```

### GET `/paths/current`

用途：获取当前用户某门课程最新 `active` 学习路径。无路径时返回真实空状态，不生成假路径。

查询参数：

- `course_id`：必填。

空状态响应：

```json
{
  "data": {
    "course_id": "101",
    "status": "not_started",
    "message": "学习路径尚未生成。",
    "path": null,
    "tasks": [],
    "evidence_summary": {
      "knowledge_point_count": 6,
      "confirmed_or_reviewing_weakness_count": 0,
      "pending_weakness_count": 1,
      "resource_count": 0,
      "basis": []
    },
    "agent_trace_id": null
  },
  "trace_id": "trace_path_current"
}
```

### PATCH `/paths/tasks/{task_id}`

用途：更新当前用户自己的路径任务状态。非本人任务返回 404；状态只能为 `todo`、`doing`、`completed`。

请求：

```json
{
  "status": "completed"
}
```

响应为更新后的任务对象，字段同 `tasks[]` 元素。

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
  "title": "帮我整理这份期末资料",
  "selected_material_ids": [12, 15]
}
```

规则：

- `scope=home` 时 `course_id` 必须为空，当前 `/app` 首页首次发送会先创建主页会话。
- `selected_material_ids` 可选，只允许绑定当前用户已解析资料，去重后最多 10 份；课程会话不允许绑定主页资料。
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
    "selected_material_ids": [12, 15],
    "created_at": "2026-07-03T08:00:00Z",
    "updated_at": "2026-07-03T08:00:00Z"
  },
  "trace_id": "trace_xxx"
}
```

### GET `/tutor/sessions`

用途：查看会话列表。支持按 `scope` 和 `course_id` 筛选主页历史或课程内历史。Phase 4.3 已接入 `scope=home`，用于左侧主页历史；Phase 5.3 已接入 `scope=course&course_id=...`，用于课程空间侧栏和课程内历史；只返回当前用户自己的未归档会话。

查询参数：

- `scope`：`home` 或 `course`，默认 `home`。
- `course_id`：课程会话筛选参数，主页历史不传。

### GET `/tutor/sessions/history`

用途：分页读取当前用户全部未归档主页会话。该接口供主页及其他 `PageFrame` 侧栏共用，不替代课程空间继续使用的 `GET /tutor/sessions?scope=course&course_id=...`。

查询参数：

- `page`：默认 `1`。
- `page_size`：默认 `30`，最大 `50`。
- `q`：可选搜索词，最长 100 字；同时匹配会话标题和 user/assistant 消息正文。

响应返回 `items`、`page`、`page_size`、`total`、`has_more`。搜索结果可包含不超过 120 字的 `match_snippet`，只用于显示安全匹配片段，不返回完整消息正文；结果按 `updated_at`、`id` 倒序稳定排列。

### GET `/tutor/sessions/{session_id}`

用途：查看会话详情。Phase 4.3 已用于点击左侧主页历史后恢复主页消息列表；Phase 5.3 已用于点击课程内历史后恢复课程消息和 `citation_json` 引用。只能访问当前用户自己的未归档会话。

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
      "selected_material_ids": [12, 15],
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

### PATCH `/tutor/sessions/{session_id}`

用途：更新 AI 学习会话标题或主页会话参考资料。用于历史会话菜单和主页资料确认；必须携带 JWT，只能修改当前用户自己的未归档会话。

请求：

```json
{
  "title": "反向传播薄弱点复习",
  "selected_material_ids": [12, 15]
}
```

规则：

- `title` 会去掉首尾空白，不能为空，最长 255 个字符。
- `title` 与 `selected_material_ids` 均可选，但至少提交一项；显式空数组表示清空会话参考资料。
- 资料保存前验证当前用户归属和 `parse_status=completed`；课程会话传入非空资料数组返回 `MATERIAL_CONTEXT_INVALID`。
- 成功后返回更新后的 `TutorSessionSummary`。
- 会话不存在、属于其他用户或已归档时返回 404。

### DELETE `/tutor/sessions/{session_id}`

用途：删除历史会话。当前实现为软删除：会话会从主页历史或课程空间历史隐藏，后续列表、详情和继续发送都不可再访问；消息数据不作为页面历史返回。

响应：

```json
{
  "data": {
    "session_id": "12",
    "deleted": true
  },
  "trace_id": "trace_xxx"
}
```

规则：

- 必须携带 JWT，只能删除当前用户自己的未归档会话。
- 会话不存在、属于其他用户或已归档时返回 404。
- 删除当前前端选中的会话后，主页回到默认学习入口；课程空间回到课程问答引导态。

### POST `/tutor/sessions/{session_id}/messages`

用途：发送问题并获取完整回答。主页和课程会话都复用当前路径；前端默认使用下方流式接口，本接口保留为兼容和自动化测试路径。`scope=home/course` 都先由 `SemanticDecisionService` 使用当前用户有效回答模型输出结构化意图、搜索词、联网和推理模式；每条消息最多一次额外路由调用。`HomeTutorGraph` 随后处理资料、网页、规划和回答，`CourseTutorGraph` 优先执行严格课程 RAG，并只在证据策略允许时加入明确标注的外部补充。

请求：

```json
{
  "message": "为什么反向传播要用链式法则？",
  "selected_material_ids": [12, 15]
}
```

当前响应返回完整会话详情。

主页会话规则：

- assistant 内容来自模型通用知识和本次可用证据；无可用模型配置时保存清晰提示。
- `selected_material_ids` 只允许当前用户资料，最多 10 个。省略时沿用会话已保存范围，显式数组替换范围，空数组清空。历史资料失效时只忽略失效项并返回安全 warning，不泄露资料归属。后端从 `material_chunks` 检索与上下文化 query 相关的最多 5 个片段，不再固定截取资料开头；无相关片段时返回空资料引用。
- 前端不再发送 `use_web_search` 或 `deep_thinking`。两个字段已废弃但继续接收：`true` 为旧客户端强制启用，`false` 或缺省均由 `ToolDecision` 自动判断。
- 时效信息、明确检索/核实请求自动调用 `WebSearchService`；复杂比较、推导、诊断、规划与多证据综合进入 deep。未配置 `WEB_SEARCH_API_KEY` 时返回 warning，不生成假网页来源。
- `planner` 只保存目标、证据需求和回答结构摘要，不展示原始思维链、系统提示词或完整模型输入。
- `citation_json` 允许课程、资料、网页三类真实来源。资料来源可包含 `source_type`、`material_id`、`title`、`section_title`、`page_number`、`snippet`、`score`、`retrieval_source`、`embedding_status`、`embedding_provider`、`embedding_dimension`、`rerank_score` 和 `rerank_status`；网页来源可包含 `title`、`url`、`snippet`。
- 回答使用 `<final_answer>` 边界隔离内部输入。ReviewAgent 检查 `prompt_echo`、`off_topic`、`malformed_markdown`、`citation_mismatch`、`fake_web_source`、`sensitive_output`；不通过时最多修订一次，第二次仍不通过时返回安全降级回答。
- 成功时 assistant `trace_id` 写入真实 Graph trace。主页正常节点为 `context -> route -> material_retriever -> web_search -> planner -> answer -> review -> persist`；课程节点为 `profile -> route -> retriever -> web_search -> planner -> tutor -> weakness -> review -> next_action`。
- 模型调用失败时返回可恢复错误，不写入半截 assistant 消息。
- 同一 `session_id` 内默认启用多轮上下文。后端会读取最近 12 条 user/assistant 消息，单条最多 1200 字，总历史上下文最多 6000 字；更早历史只生成最多 1500 字的安全摘要。请求体不新增字段，前端不展示历史原文。

课程会话规则：

- 命中课程知识切片时，assistant `citation_json` 采用 `/rag/search` 的结果字段结构，并可包含关键词、向量、RRF 与重排序状态；所有引用仍绑定真实 chunk ID。
- 同会话真实消息先按模型上下文预算裁剪；`SemanticDecisionService` 输出 `standalone_query`、`uses_history` 和 `referenced_turn_ids`。课程 RAG 与搜索只使用模型改写后的必要问题，不再按固定代词或最近两问拼接。
- 无命中时 `citation_json=[]`，assistant 内容提示“资料依据不足”，前端不得伪造引用。
- 有命中且可解析模型配置时，assistant `content` 保存模型基于引用生成的回答，`trace_id` 写入本次 `CourseTutorGraph` trace。
- 有命中但无可用模型配置时，assistant 保存“已找到资料依据，但当前未配置可用模型。”，引用仍保留。
- 模型调用超时、鉴权失败、非 JSON、空内容或流式中途失败时返回 `MODEL_PROVIDER_ERROR`，前端保留输入，不写入半截 assistant 消息。
- 课程空间刷新后，前端通过 `GET /tutor/sessions/{session_id}` 恢复消息和引用。

低依据判断、完整 Agent trace 和 ReviewAgent 已在 `CourseTutorGraph` / 资源 Graph 的安全轨迹中接入；动态维度 Embedding、讯飞原生 2560 维协议和可选重排序已经接入。

### POST `/tutor/sessions/{session_id}/messages/stream`

用途：SSE 流式返回主页或课程空间回答。必须携带 JWT，请求体沿用普通消息接口；主页和课程空间都由后端自动能力策略决定联网和推理强度，前端只发送问题及可选资料范围。旧 true 工具字段在两种 scope 下都只表示强制启用兼容。

```json
{
  "message": "启发式搜索怎么复习？"
}
```

响应类型：

```text
Content-Type: text/event-stream
```

课程会话保持兼容顺序：

```text
event: metadata
data: {"session_id":"12","trace_id":"trace_xxx","workflow":"course_tutor","artifact_type":"chat_message","steps":["profile","retriever","tutor","weakness","review","next_action"],"citation_count":2,"used_model":true,"context_message_count":4,"context_summary_used":false,"retrieval_query_mode":"contextual"}

event: token
data: {"content":"可以先从启发函数的作用看起。"}

event: done
data: {"session":{},"messages":[]}
```

主页会话事件顺序：

```text
metadata -> status* -> sources -> token* -> replace? -> done
```

- `metadata`：包含 `workflow=home_tutor`、Graph 步骤、`context_message_count`、`context_summary_used` 和 `retrieval_query_mode`，不包含历史全文或模型输入。
- `status`：只返回“正在检索资料、正在联网搜索、正在组织回答、正在审核回答”等安全阶段。
- `sources`：返回本次真实 `citations` 和工具 `warnings`。
- `token`：只在确认进入 `<final_answer>` 后发送 Markdown 正文。
- `replace`：仅当 ReviewAgent 修订草稿时发送，结构为 `{"content":"...","reason":"review_repair"}`。
- `done`：返回已持久化的完整 `TutorSessionDetail`，前端用它校准临时消息。

错误事件：

```text
event: error
data: {"code":"rate_limited","message":"模型服务请求较多，请稍后重试。","retryable":true,"retry_after_seconds":3}
```

流式规则：

- 后端先检索课程知识切片，再决定是否调用模型；Phase 6.4 后检索优先走混合召回，失败时退回关键词检索。
- 无引用时不调用模型，流式返回“资料依据不足”，并持久化 user 消息和 assistant 提示，`citation_json=[]`。
- 有引用但未配置可用模型时不调用外部模型，流式返回未配置提示，仍持久化真实引用。
- 有引用且模型可用时，Provider 以 `stream=true` 调用 `{base_url}/chat/completions`，逐段解析 `data: {...}` 和 `[DONE]`。
- 只有流式成功完成后，后端才持久化 user 消息、完整 assistant 回答、真实引用和 `trace_id`。
- `error` 向后兼容保留 `code` 和 `message`，新增 `retryable` 与可选 `retry_after_seconds`。安全类别包括未配置、认证失败、上下文过长、限流、繁忙、超时、网络故障、服务故障、无效响应和流中断。
- 模型流式中途失败时只发送 `error` 事件，不写入半截 assistant；首 token 后不自动重放，前端必须保留输入并提供明确恢复动作。
- `done` 事件返回最终 `TutorSessionDetail`，前端用它替换临时流式状态并刷新课程历史。
- 主页只有 Graph 完成 Review/Repair 后才持久化 user/assistant 消息；流式中途失败只发送 `error`，不保存半截消息。

## 14. Practice 与 Report 接口

状态：Phase 14 已升级。路由保持不变，`AssessmentGraph` 和 `ReportGraph` 已接管生产流程，`PathPlanningGraph` 负责练习后的独立路径回流。

统一规则：

- 所有接口必须携带 JWT。
- 只能创建、读取和提交当前用户自己课程下的练习。
- 只能生成和读取当前用户自己课程下的报告。
- 练习题先从真实课程切片生成证据型蓝图，包含知识点、能力目标、引用和不可变规则答案；模型可增强题面、合理干扰项和解析，数字评分始终采用确定性规则。
- 练习题第一刀支持 `single_choice`、`multiple_choice`、`short_answer`。
- 练习提交后，低分或错误题会按课程和知识点合并进入 `weakness_review_queue`，并用 `source_ref_type="practice_answer"`、`source_ref_id` 和 `diagnosis_json` 保存安全证据；已有普通路径会在独立 trace 中重排，无路径时不自动创建。
- `in_progress` 练习的 `correct_answer` 始终为 `null`，避免答题前泄题；只有练习完成后，提交和读取响应才返回当前题目的正确答案，用于错题复盘。
- 响应不保存或返回系统提示词、模型输入、API Key、完整课程资料原文或完整用户画像原文。

### POST `/practice/sessions`

用途：创建当前用户课程练习，并返回题目。题目由真实课程切片和知识点证据形成蓝图，再经模型增强、重复率/选项/答案/引用门禁和 ReviewAgent 审核。

请求：

```json
{
  "course_id": 1,
  "knowledge_point_ids": [8],
  "question_count": 5,
  "difficulty": "adaptive"
}
```

响应：

```json
{
  "data": {
    "id": "501",
    "course_id": "101",
    "title": "数据结构与算法练习",
    "status": "in_progress",
    "score": null,
    "requested_difficulty": "adaptive",
    "effective_difficulty": "easy",
    "draft_saved_at": null,
    "questions": [
      {
        "id": "q1",
        "question_type": "single_choice",
        "knowledge_point_id": "8",
        "knowledge_point_title": "启发式搜索",
        "prompt": "A* 搜索中，哪一项正确描述了 f(n)=g(n)+h(n)？",
        "options": ["g(n) 表示已走代价，h(n) 表示剩余代价估计", "g(n) 与 h(n) 都只表示节点深度", "h(n) 表示已走代价，g(n) 表示目标概率", "f(n) 与路径代价无关"],
        "correct_answer": null,
        "keywords": ["启发式搜索", "关键概念"],
        "explanation": "课程证据说明 g(n) 是已走代价，h(n) 是剩余代价的启发估计。",
        "difficulty": "medium",
        "citation_refs": ["302"],
        "generation_mode": "model_enhanced",
        "prompt_version": "assessment-v3.1",
        "quality": {"evidence_bound": true, "answer_locked": true}
      }
    ],
    "answers": [],
    "agent_trace_id": "trace_practice_session",
    "created_at": "2026-07-05T10:00:00Z",
    "updated_at": "2026-07-05T10:00:00Z"
  },
  "trace_id": "trace_practice_session"
}
```

错误：

- 未登录返回 401。
- 课程不存在、非本人课程或跨课程知识点返回 404。
- 题量或难度非法返回 400。

### GET `/practice/sessions/{session_id}`

用途：读取当前用户自己的练习、题目、作答和反馈。非本人练习返回 404。

### GET `/practice/sessions/latest?course_id=...`

用途：返回当前用户当前课程最近的练习，优先返回未完成会话；没有练习时 `data=null`。前端用它恢复刷新前的学习位置。

### GET `/practice/sessions/recent?course_id=...&limit=5`

用途：按更新时间从新到旧返回当前用户当前课程最近已完成的练习摘要，供学习报告实时趋势使用。`limit` 默认为 5，范围为 1–20。

响应只包含 `id`、`course_id`、`title`、`status`、`score`、`grading_status`、`effective_difficulty`、`created_at` 和 `updated_at`，不返回题目、作答正文或诊断原文。课程不存在或不属于当前用户时返回 404。

### PATCH `/practice/sessions/{session_id}/draft`

用途：保存未评估答案草稿，不触发评分、弱点、路径或画像回流。仅 `in_progress` 会话可写，完成后的练习返回 400。

```json
{"answers":[{"question_id":"q1","answer_text":"我的草稿"}]}
```

### POST `/practice/sessions/{session_id}/answers`

用途：提交答案，写入 `practice_answers`，更新 `practice_sessions.status/score`，并把低分或错误题反哺到课程级弱点队列。

成功响应中 `status="completed"`，题目 `correct_answer` 恢复为真实答案；前端据此标绿正确选项、标红错误选择，并在错题详情展示正确答案。客观评分仍以服务端确定性结果为准。

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

规则：

- 客观题按标准答案确定性批改。
- 多选题使用逗号分隔答案，至少覆盖标准答案才算正确；部分覆盖按命中比例给分。
- 所有简答题在一次提交中批量交给当前用户有效回答模型，依据题目、课程证据、参考答案和明确量规进行语义评分；关键词兼容字段不参与判分。
- 模型输出必须通过题目 ID、0–100 分、正确性、字段白名单和引用集合校验；缺项、伪造引用、非法结构或调用失败时，该简答题为 `score=null`、`is_correct=null`、`grading_status="ungraded"`。
- 未评分简答题排除总分分母，不进入弱点、画像、掌握度、报告趋势或路径重排；没有任何已评分题时会话 `score=null`。
- 空答案或提交不属于当前练习的题目返回 400。
- 当前实现允许重复提交同一练习，后一次提交会替换本练习的作答记录并重算分数。

响应仍为 `PracticeSessionDetail`，`status` 变为 `completed`，`score` 为全部已评分题的平均分，`grading_status` 为 `complete | partial | ungraded`。每条反馈包含 `grading_status=deterministic|model|ungraded`、可空 `score`、`matched_concepts`、`missing_concepts`、可空 `confidence`，并暂时保留 `matched_keywords/missing_keywords` 兼容字段。低分题可选增加：

```json
{
  "diagnosis": {
    "misconception": "回答尚未覆盖启发式搜索的关键依据。",
    "missing_concepts": ["启发函数"],
    "recommended_action": "先复习课程引用，再完成一道同类练习。",
    "confidence": 0.66,
    "evidence_ref": {"type": "practice_answer", "id": "601"}
  }
}
```

会话级可选 `closure_update`：

```json
{
  "weaknesses_added": 1,
  "weaknesses_updated": 0,
  "path_update_status": "replanned",
  "path_agent_trace_id": "trace_path_replan",
  "recommended_resource_ids": ["801"]
}
```

`path_update_status` 为 `not_started | replanned | unchanged | failed`。路径失败不影响已完成练习和弱点更新。

### POST `/practice/sessions/{session_id}/regrade`

用途：幂等重试当前用户该练习中仍为 `ungraded` 的简答题。接口使用已保存答案，不接收新的作答正文；成功后原子更新对应反馈、重新计算已评分题平均分，并只对本次新评分结果执行一次弱点、画像候选和既有路径闭环。没有未评分题时直接返回当前结果；模型仍不可用时保留原有部分评分状态。

### POST `/reports/generate`

用途：由 `ReportGraph` 聚合当前课程最近 5 次已完成练习、掌握度、弱点、当前路径和资源，写入 `assessment_reports`。练习会话、已作答题、正确题、已评估知识点和已完成路径任务分别统计并锁定；模型只增强总结与建议，数字矛盾必须修订或退回确定性报告。

请求：

```json
{
  "course_id": 1,
  "practice_session_id": 1
}
```

响应：

```json
{
  "data": {
    "id": "801",
    "course_id": "101",
    "practice_session_id": "501",
    "status": "ready",
    "score": 67,
    "report": {
      "summary": "本次评估得分 67，基于真实练习作答生成。",
      "mastery_update": {
        "weak_count": 1,
        "mastered_count": 2,
        "learning_count": 4
      },
      "weakness_list": [
        {
          "knowledge_point_id": "8",
          "title": "启发式搜索",
          "source_type": "practice_assessment"
        }
      ],
      "evidence_refs": [
        {
          "practice_answer_id": "601",
          "knowledge_point_id": "8",
          "score": 0
        }
      ],
      "next_step_suggestions": ["优先复习《数据结构与算法》中得分较低的知识点。"],
      "trend": {
        "direction": "improved",
        "score_delta": 12,
        "sessions_compared": 3,
        "scores": [55, 61, 67]
      },
      "evidence_summary": {
        "practice_count": 3,
        "answer_count": 15,
        "correct_answer_count": 9,
        "assessed_knowledge_point_count": 4,
        "completed_path_task_count": 2,
        "weakness_count": 1,
        "path_status": "active",
        "resource_count": 2
      },
      "deterministic_statistics": {
        "practice_session_count": 3,
        "answered_question_count": 15,
        "correct_answer_count": 9,
        "assessed_knowledge_point_count": 4,
        "completed_path_task_count": 2
      },
      "review_result": {
        "review_status": "passed",
        "confidence": 0.91,
        "risk_flags": [],
        "safety_summary": "统计数字与练习证据一致。"
      },
      "review_queue_updates": [],
      "profile_changes": ["练习结果可作为后续画像证据，但本阶段不自动改写用户长期画像。"]
    },
    "agent_trace_id": "trace_report",
    "created_at": "2026-07-05T10:10:00Z"
  },
  "trace_id": "trace_report"
}
```

错误：

- 未登录返回 401。
- 课程不存在、非本人课程、指定练习不存在或练习不属于当前课程返回 404。

### GET `/reports/latest`

用途：获取当前用户当前课程最新学习报告。

查询参数：

```text
course_id=101
```

无报告时返回真实空状态：

```json
{
  "data": {
    "id": null,
    "course_id": "101",
    "practice_session_id": null,
    "status": "empty",
    "score": null,
    "report": {
      "summary": "还没有真实学习报告。",
      "mastery_update": {
        "weak_count": 0,
        "mastered_count": 0,
        "learning_count": 0
      },
      "weakness_list": [],
      "evidence_refs": [],
      "next_step_suggestions": ["完成一次课程练习后生成报告。"],
      "review_queue_updates": [],
      "profile_changes": []
    },
    "agent_trace_id": null,
    "created_at": null
  },
  "trace_id": "trace_report_latest"
}
```

## 15. Weakness Review 接口

状态：Phase 7.4 已实现课程绑定的弱点复习队列操作接口。当前接口只处理确认、开始、完成和忽略；Phase 10 后练习评估可以写入 `practice_assessment` 来源的 `confirmed` 复习项，但队列操作接口本身仍不生成学习路径、资源、练习或报告。

### POST `/courses/{course_id}/weakness-review-items/{item_id}/confirm`

用途：确认某个 `pending` 待确认项是当前课程的薄弱点，状态变为 `confirmed`。

规则：

- 必须携带 JWT。
- 只能操作当前用户自己的课程和该课程下的队列项。
- 无权限、课程不存在、跨课程队列项或其他用户队列项统一返回 404。
- 非法状态流转返回 400。

### POST `/courses/{course_id}/weakness-review-items/{item_id}/start`

用途：开始复习某个弱点项，状态变为 `reviewing`。允许从 `pending` 或 `confirmed` 进入。

### POST `/courses/{course_id}/weakness-review-items/{item_id}/complete`

用途：完成本轮复习，状态变为 `completed`。允许从 `pending`、`confirmed` 或 `reviewing` 进入。

### POST `/courses/{course_id}/weakness-review-items/{item_id}/dismiss`

用途：忽略或移除某个弱点项，状态变为 `dismissed`。这是软忽略，不物理删除；重复忽略同一项幂等返回当前项。

响应：

```json
{
  "data": {
    "id": "701",
    "title": "启发式搜索",
    "status": "confirmed",
    "source_type": "course_question",
    "course_id": "7",
    "knowledge_point_id": "401",
    "next_review_at": null,
    "created_at": "2026-07-05T08:30:00Z",
    "updated_at": "2026-07-05T08:40:00Z"
  },
  "trace_id": "trace_20260705_074"
}
```

状态流转：

- `pending -> confirmed | reviewing | completed | dismissed`
- `confirmed -> reviewing | completed | dismissed`
- `reviewing -> completed | dismissed`
- `completed -> dismissed`
- `dismissed` 只允许重复 `dismiss`，不允许再开始或完成。

## 16. 已退役接口

`/exam-sprint/*` 已停止注册。日常学习统一使用 `/paths/*` 个性化学习路径；历史 `sprint_active/sprint_archived` 数据保留但不再通过业务接口读取或更新。
## 17. Export 接口

状态：异步任务支持 Markdown、PDF、DOCX 学习档案和资源 PPTX。旧 `POST /exports/learning-dossier` Markdown 同步接口保留兼容；所有异步文件都写入 `export_jobs` 并由 Redis/RQ worker 渲染。

统一规则：

- 必须携带 JWT。
- 只能导出当前用户自己的课程。
- 导出内容来自课程信息、最新学习报告、知识点数量、弱点队列、当前 active 学习路径任务、同课程资源和练习证据摘要。
- 没有学习报告时仍返回真实空状态，不伪造分数或诊断结论。
- 响应不包含完整资料原文、完整作答原文、内部指令、模型请求内容、密钥、登录令牌或完整用户画像。

### POST `/exports/learning-dossier`

用途：兼容导出课程级 Markdown 学习档案。前端新版报告页默认使用异步 job，本接口保留给旧调用和自动化兼容路径。

请求：

```json
{
  "course_id": 1
}
```

响应：

```json
{
  "data": {
    "course_id": "101",
    "filename": "edunova-数据结构与算法-learning-dossier.md",
    "content_type": "text/markdown; charset=utf-8",
    "markdown": "# 数据结构与算法 学习档案\n\n## 数据概览\n...",
    "generated_at": "2026-07-05T15:00:00Z",
    "agent_trace_id": "trace_export",
    "source_summary": {
      "has_report": true,
      "report_id": "801",
      "knowledge_point_count": 12,
      "weakness_count": 2,
      "path_task_count": 7,
      "resource_count": 5,
      "practice_answer_count": 10
    }
  },
  "trace_id": "trace_export"
}
```

错误：

- 未登录返回 401。
- 课程不存在或不属于当前用户返回 404。

### POST `/exports/learning-dossier/jobs`

用途：创建学习档案异步导出任务。`format` 支持 `markdown`、`pdf`、`docx`。任务创建后入队 RQ；测试环境可同步执行。

请求：

```json
{
  "course_id": 1,
  "format": "pdf"
}
```

响应：

```json
{
  "data": {
    "job_id": "901",
    "status": "queued",
    "format": "pdf",
    "export_type": "learning_dossier",
    "resource_id": null,
    "filename": "edunova-数据结构与算法-learning-dossier.pdf",
    "content_type": "application/pdf",
    "agent_trace_id": "trace_export_job",
    "error_message": null,
    "created_at": "2026-07-07T10:00:00Z",
    "updated_at": "2026-07-07T10:00:00Z",
    "completed_at": null
  },
  "trace_id": "trace_export_job"
}
```

### GET `/exports/{job_id}`

响应字段同创建任务响应。`export_type` 为 `learning_dossier` 或 `resource_artifact`，资源 PPTX 会返回 `resource_id`。`status` 为 `queued`、`running`、`completed` 或 `failed`；失败时只返回安全摘要。

### GET `/exports/{job_id}/download`

用途：下载已完成的学习档案或资源文件。只允许下载当前用户自己的 `completed` 任务；`Content-Type` 根据格式返回 Markdown、PDF、DOCX 或 PPTX 对应 MIME。

## 18. Settings 接口

### GET `/settings/model`

用途：获取当前有效模型设置摘要。该兼容接口分别解析回答默认和向量默认；某一用途没有个人默认时，只回退对应的 `.env` 系统配置。两种用途可以来自同一套组合配置、不同配置或不同服务器连接。响应不会返回明文 API Key。前端 Provider 预设首位为讯飞星火 Spark，但后端协议仍统一保存为 `openai_compatible`。

响应：

```json
{
  "data": {
    "source": "user",
    "provider": "openai_compatible",
    "base_url": "https://api.example.com/v1",
    "chat_model": "gpt-4.1-mini",
    "embedding_provider": "openai_compatible",
    "embedding_base_url": "https://embedding.example.com/v1",
    "embedding_model": "example-embedding-model",
    "has_api_key": true,
    "api_key_masked": "sk-u...cret",
    "has_embedding_api_key": true,
    "embedding_api_key_masked": "em-u...cret",
    "can_use_model": true,
    "can_use_embedding_model": true
  },
  "trace_id": "trace_settings_001"
}
```

### PUT `/settings/model`

用途：保存当前用户默认 OpenAI-compatible 模型设置。该兼容接口支持回答与向量两组独立连接；如果没有填写 `embedding_base_url`、`embedding_provider` 和 `embedding_api_key`，旧客户端继续让向量用途复用回答连接。两组 Key 分别使用 Fernet 加密；连接未变化时，对应 Key 为空字符串或缺省会保留原密钥。向量模型缺省时使用关键词检索 fallback。

请求：

```json
{
  "provider": "openai_compatible",
  "base_url": "https://spark-api-open.xf-yun.com/v1",
  "api_key": "example-key",
  "chat_model": "lite",
  "embedding_provider": "openai_compatible",
  "embedding_base_url": "https://embedding.example.com/v1",
  "embedding_api_key": "example-embedding-key",
  "embedding_model": "example-embedding-model"
}
```

响应同 `GET /settings/model`，不返回明文 API Key。

### POST `/settings/model/test`

用途：测试当前有效模型连通性。请求体省略时测试当前回答默认配置；`operation=embedding` 或 `operation=rerank` 时分别测试当前向量或重排序默认配置。对应用途没有个人默认时分别回退服务器配置。显式探测不自动重试，也不跨 Provider 切换。

可选请求：

```json
{ "operation": "chat" }
```

`operation` 可为 `chat`、`embedding` 或 `rerank`。未配置某项能力时返回安全的 `not_configured`，不影响其他能力状态；向量测试成功后会保存实际维度。

响应：

```json
{
  "data": {
    "ok": true,
    "source": "user",
    "chat_model": "gpt-4.1-mini",
    "operation": "chat",
    "model": "gpt-4.1-mini",
    "code": null,
    "retryable": false,
    "tested_at": "2026-07-13T10:00:00Z",
    "message": "AI 服务连接正常。",
    "config_id": 1
  },
  "trace_id": "trace_settings_002"
}
```

### GET `/settings/model/configs`

用途：读取当前用户所有模型配置和系统默认服务摘要。必须携带 JWT。每条配置可包含回答、向量和重排序三组独立连接；所有 Key 只返回脱敏状态。`can_use_model`、`can_use_embedding_model` 和 `can_use_rerank_model` 分别表示三项能力。

响应：

```json
{
  "data": {
    "configs": [
      {
        "id": 1,
        "source": "user",
        "display_name": "星火回答 + 通义向量",
        "preset_id": "spark",
        "provider": "openai_compatible",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "chat_model": "lite",
        "embedding_provider": "openai_compatible",
        "embedding_preset_id": "qwen",
        "embedding_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "embedding_model": "text-embedding-v4",
        "has_api_key": true,
        "api_key_masked": "sp-u...oken",
        "has_embedding_api_key": true,
        "embedding_api_key_masked": "qw-u...oken",
        "can_use_model": true,
        "can_use_embedding_model": true,
        "is_default": true,
        "is_embedding_default": true,
        "last_test_ok": true,
        "last_test_message": "AI 服务连接正常。",
        "last_tested_at": "2026-07-13T10:00:00Z",
        "connection_tests": {
          "chat": {
            "operation": "chat",
            "ok": true,
            "model": "lite",
            "message": "AI 服务连接正常。",
            "code": null,
            "retryable": false,
            "tested_at": "2026-07-13T10:00:00Z"
          }
        }
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
      "can_use_model": false,
      "can_use_embedding_model": false
    },
    "default_config_id": 1,
    "default_chat_config_id": 1,
    "default_embedding_config_id": null
  },
  "trace_id": "trace_settings_configs"
}
```

### POST `/settings/model/configs`

用途：创建当前用户的一条模型配置方案。`display_name` 在同一用户内不能重复；回答、向量和重排序至少填写一项。三项能力分别接受自己的 Provider、预设、Base URL、Key 和模型，因此同一方案可组合不同服务商。`make_default`、`make_embedding_default`、`make_rerank_default` 只影响各自用途。

请求：

```json
{
  "display_name": "星火回答 + 通义向量",
  "preset_id": "spark",
  "provider": "openai_compatible",
  "base_url": "https://spark-api-open.xf-yun.com/v1",
  "api_key": "example-key",
  "chat_model": "lite",
  "embedding_provider": "openai_compatible",
  "embedding_preset_id": "qwen",
  "embedding_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "embedding_api_key": "example-embedding-key",
  "embedding_model": "text-embedding-v4",
  "make_default": true,
  "make_embedding_default": true
}
```

响应：返回单条配置摘要，不返回明文 API Key。

### PATCH `/settings/model/configs/{config_id}`

用途：更新当前用户自己的模型配置。只允许访问当前用户的配置；跨用户配置返回 404。连接未变化时，回答、向量和重排序空 Key 分别保留原密钥；Provider 或 Base URL 变化且没有新 Key 时清除该用途旧密钥。

### POST `/settings/model/configs/{config_id}/default`

用途：把当前用户自己的某条配置设为回答默认，并取消同用户其他回答默认项。主页、课程问答和生成型 Graph 优先使用回答默认；不存在时回退服务器 `.env` 回答配置。`default_config_id` 继续作为 `default_chat_config_id` 的兼容别名。

### POST `/settings/model/configs/{config_id}/embedding-default`

用途：把包含 `embedding_model` 的配置设为向量默认，并取消同用户其他向量默认项。资料与课程 RAG 从该配置的 `embedding_*` 字段解析 Provider、Base URL、Key 和向量模型；旧共享连接记录由迁移兼容。不存在个人向量默认时独立回退服务器 `.env` 向量配置。

### POST `/settings/model/configs/{config_id}/rerank-default`

用途：把包含 `rerank_model` 的配置设为重排序默认，并取消同用户其他重排序默认项。不存在个人重排序默认时独立回退服务器配置；未配置时 RAG 继续使用 RRF 混合排序。

### POST `/settings/model/embedding/reindex-jobs`

用途：使用当前用户的默认向量配置显式重建其课程和资料切片向量。请求体为 `{ "config_id": number | null }`，并支持 `Idempotency-Key`；返回现有 `AiJobResponse`，`workflow=embedding_reindex`。任务支持进度、取消、刷新恢复和失败重试，切换默认配置本身不会自动创建任务。

### POST `/settings/model/configs/{config_id}/test`

用途：测试指定模型配置。三项结果分别写入 `connection_test_json.chat`、`embedding`、`rerank`。旧 `last_test_*` 继续映射回答模型最近测试；其他测试不会覆盖回答状态。修改对应连接后只清除该项旧测试摘要。

### DELETE `/settings/model/configs/{config_id}`

用途：删除当前用户自己的某条模型配置。若该配置承担回答或向量默认，对应用途分别选择剩余的可用配置；没有候选时独立回退服务器配置。

模型 Provider 第一版按 OpenAI-compatible 协议实现：

- 聊天回答：`{base_url}/chat/completions`。
- 向量生成：讯飞使用原生签名地址；兼容服务使用 `{embedding_base_url}/embeddings`。
- 重排序：硅基使用 `/v1/rerank`，百炼使用 Workspace `/compatible-api/v1/reranks`。
- 回答运行时优先使用当前用户回答默认配置。
- Embedding 运行时优先使用当前用户向量默认配置。
- 某一用途没有个人默认时，仅该用途回退服务器 `.env` 兜底配置。

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
- 默认回答预设：Spark X2-Flash，Base URL `https://spark-api-open.xf-yun.com/agent/v1/`，模型 `spark-x`。

讯飞 LLM Embedding 使用 APPID、APIKey、APISecret 签名鉴权，资料 `para`、问题 `query`，返回 2560 维；三项凭证均加密保存且不通过 API 明文返回。

## 19. AI 长任务接口

状态：Phase 17 已完成。所有接口必须携带 JWT，并按当前用户隔离。

### POST `/courses/from-materials/jobs`

用途：异步运行 `CourseBuilderGraph`。请求体与同步建课接口相同，必须携带 `Idempotency-Key`；成功返回 HTTP 202。

### POST `/resources/generation-jobs`

用途：异步运行 `ResourceGenerationGraph`。请求体与同步资源生成接口相同，包含可选版本动作与来源资源，必须携带 `Idempotency-Key`；成功返回 HTTP 202。任务请求摘要会保存 `generation_action/source_resource_id` 以支持刷新与安全重试。单个 Worker 失败但仍有成功资源时任务为 `completed`，失败类型写入结果；全部失败才为 `failed`。

### POST `/paths/generation-jobs`

用途：异步运行 `PathPlanningGraph`。请求体为 `GeneratePathRequest`，必须携带 `Idempotency-Key`，成功返回 HTTP 202。手动生成和练习后重排共用 `workflow=path_planning`；评分接口不等待该任务，排队失败只返回 warning。任务每次最多一次路径模型调用，取消或失败保留原 active 路径。

Phase 29 起 `AiJobWorkflow` 增加 `path_planning`。来源引用可携带 `access_scope=mainland_preferred|mainland_community|global_source|external_fallback`；该字段是策略分层，不表示实时网络可达性。

### POST `/paths/tasks/{task_id}/resource-jobs`

用途：为当前用户有效路径中的进行中任务生成“本节学习安排”尚未就绪的资源。无请求体，必须携带 `Idempotency-Key`，成功返回既有 `AiJobResponse` 和 HTTP 202。

服务端从任务中读取知识点、难度、教学策略、学习目标和有序资源类型；已完成且可访问的资源不会重复生成。同一任务已有 `queued/running/cancelling` 的资源任务时返回该任务。已完成任务、归档路径、空安排或全部资源就绪分别返回 409/400。结果中的 `path_task_id` 用于任务托盘返回资源工坊并恢复本节上下文。

`LearningBundle.items[*].learning_status` 为 `not_started|in_progress|completed`，`ready_count` 和 `completed_count` 由当前用户、当前路径任务的 `resource_interactions` 聚合；它们不改变资源本身或路径任务状态。

### GET `/ai-jobs?status=active&limit=20`

用途：恢复当前用户排队、运行、取消中和失败任务。`limit` 范围 1 至 50。

### GET `/ai-jobs/{job_id}`

用途：查询单条任务。跨用户或不存在返回 404。

### GET `/ai-jobs/{job_id}/events`

用途：返回鉴权 SSE。事件为 `snapshot`、`done`、`error`、`cancelled`，空闲期间发送心跳注释；断线后客户端通过详情/列表 GET 降级恢复。

### POST `/ai-jobs/{job_id}/cancel`

用途：请求协作式取消。排队任务直接取消；运行任务进入 `cancelling`，当前模型请求可在超时内结束，但下一节点或持久化前必须停止。

### POST `/ai-jobs/{job_id}/retry`

用途：为 `failed` 或 `cancelled` 任务创建新任务，返回 HTTP 202，并通过 `retry_of_job_id` 关联原任务。每条任务最多重试 3 次，重试前重新校验资料、课程和知识点归属。

统一任务响应：

```json
{
  "data": {
    "job_id": "101",
    "workflow": "resource_generation",
    "status": "running",
    "course_id": "8",
    "retry_of_job_id": null,
    "progress_percent": 60,
    "stage": "DocWorker",
    "label": "DocWorker 已完成",
    "steps": [
      {
        "name": "DocWorker",
        "label": "DocWorker 已完成",
        "status": "completed",
        "progress_percent": 60,
        "resource_type": "doc",
        "updated_at": "2026-07-11T10:00:00Z"
      }
    ],
    "agent_trace_id": "trace_safe",
    "request": {
      "course_id": 8,
      "knowledge_point_id": 12,
      "resource_types": ["doc"],
      "learning_goal": "掌握反向传播",
      "difficulty": "medium"
    },
    "result": {},
    "warnings": [],
    "error_code": null,
    "error_message": null,
    "attempt_count": 0,
    "can_cancel": true,
    "can_retry": false,
    "created_at": "2026-07-11T09:59:58Z",
    "updated_at": "2026-07-11T10:00:00Z",
    "started_at": "2026-07-11T09:59:59Z",
    "completed_at": null
  },
  "trace_id": "trace_api"
}
```

安全约束：响应不包含 RQ job ID、ORM 对象、原始资料、模型输入、系统提示词、密钥或思维链。排队失败会保留可重试的 `failed` 任务。每用户默认最多同时运行 2 个 AI 任务。

## 20. API 验收标准

第一版接口达到以下标准才算可进入前端联调：

1. 认证接口稳定。
2. 所有学生数据接口校验当前用户。
3. 上传资料接口能返回进度。
4. RAG 和 AI 输出接口包含引用字段。
5. 多智能体任务包含 trace_id。
6. 错误响应结构统一。
7. API Key 不以明文返回或写入日志。
8. AI 长任务和规则 fallback 能返回可恢复的安全状态。

## 21. Phase 22 API 合同

- 除 SSE 和文件下载外，所有 JSON 业务接口都声明精确 Pydantic `response_model`，并统一使用 `ApiEnvelope[T]`、分页合同或明确的领域响应模型。
- 错误继续使用 `ApiErrorEnvelope`，保留现有 HTTP 状态码、业务错误码、中文消息和 `trace_id`；`DomainError` 由全局异常处理器映射，路由不重复转换同类异常。
- `backend/openapi.json` 是前端传输类型的输入，`frontend/src/types/openapi.generated.ts` 由 `openapi-typescript` 生成。生成物不替代 Axios 拦截器、Query Key、缓存失效或页面 ViewModel。
- SSE 事件名和 JSON 数据结构保持现有合同；规范编码和分包解析不改变取消、完成、错误与轮询恢复语义。

## 22. Phase 25 搜索、来源与隐私合同

主页和课程消息接口保持原请求结构与 SSE 事件协议。`use_web_search=true/deep_thinking=true` 继续作为旧客户端强制提示；false 或缺省进入模型自动判断。响应引用新增可选字段：

```json
{
  "source_type": "web | history",
  "search_backend": "native_spark | native_openai | external",
  "evidence_role": "external_supplement | conversation_memory",
  "retrieved_at": "2026-07-15T04:00:00Z"
}
```

- `source_type=web` 必须包含可验证 HTTP(S) URL；网页只作为外部补充。
- `source_type=history` 包含历史会话与消息引用和脱敏摘要，不返回向量，不作为课程证据。
- Trace 的白名单 metadata 可包含 `search_backend`、触发方式、来源数量、`relation_type`、证据充分性和降级原因，不包含搜索 Provider 原始响应或思维链。

### `GET /api/v1/settings/privacy`

返回当前用户的跨会话记忆开关和派生索引数量：

```json
{
  "data": {
    "conversation_memory_enabled": true,
    "indexed_memory_count": 12
  },
  "trace_id": "trace_api"
}
```

### `PUT /api/v1/settings/privacy`

请求体为 `{"conversation_memory_enabled": false}`。关闭后立即停止新增与检索并删除当前用户派生记忆；开启后 best-effort 排队执行幂等回填。原始聊天记录始终保留。

### `DELETE /api/v1/settings/privacy/conversation-memory`

只删除当前用户派生记忆索引：

```json
{
  "data": {
    "deleted_count": 12,
    "raw_chat_history_preserved": true
  },
  "trace_id": "trace_api"
}
```

## 23. Phase 26 统一下一最佳行动

### `GET /api/v1/learning/next-action`

可选查询参数 `course_id`。缺省时恢复当前用户最近的资料建课或课程学习链路；提供课程时只计算该课程，课程不存在或不属于当前用户统一返回 404。

```json
{
  "data": {
    "kind": "continue_path_task",
    "status": "ready",
    "label": "继续任务：理解监督学习",
    "description": "先理解基本概念",
    "course_id": "10",
    "material_id": null,
    "knowledge_point_id": "40",
    "path_task_id": "30",
    "resource_id": "50"
  },
  "trace_id": "trace_api"
}
```

`status` 为 `ready|waiting|blocked`。`kind` 表达上传、等待解析、重试、确认目录、建课、确认薄弱点、继续路径、针对练习、生成路径、学习知识点、更新报告或查看报告等动作。接口只返回语义和安全 ID，不返回前端 URL，也不会执行动作。
# Phase 27 资源学习接口

- `GenerateResourcesRequest` 新增可选 `path_task_id`；`ResourceType` 增加 `video`。
- `LearningPathTaskResponse.learning_bundle` 返回策略、理由和有序资源项。
- `POST /api/v1/resources/{resource_id}/interactions` 接收幂等 `event_id`、`opened|started|progress|completed|feedback`、可选 `path_task_id`、0-100 进度和四类反馈。
- `GET /api/v1/resources/{resource_id}/learning-state` 返回当前用户的聚合打开、开始、完成、进度和最新反馈状态。
- `AgentTraceResponse.summary` 返回安全派生的耗时、课程/网页/历史来源数、个性化因素代码、推理模式、搜索后端、审核状态和安全摘要。

完成事件只有在资源与路径任务同属当前用户和课程且已建立关联时才推进任务；视频进度或播放器结束不会自动写完成。

## 24. Phase 28 合同收口

- `GenerateResourcesRequest.resource_types` 的 OpenAPI 枚举正式包含 `video`；前端生成类型与后端 JSON 必须通过 `scripts/check_openapi.py` 的非破坏性比较。
- `AssessmentReportContent.resource_usage_summary` 为按资源类型索引的明确结构，计数包含 `opened/started/completed/helpful/too_easy/too_hard/not_helpful`。
- 打开、开始和完成按唯一资源计数；反馈只取每个资源最近一次值，因此用户切换反馈不会制造多份证据。
- `external_video.embed_status` 使用 `unknown|available|unavailable`。后端发现合法 URL 后仍为 `unknown`，前端播放器加载结果只能更新本地展示，原平台链接始终保留。

## 25. Phase 31 行为兼容

Phase 31 不新增接口路径或数据库迁移。现有资料解析进度对大型 PDF 使用真实心跳与“正在解析大型教材”标签；练习 `score=null` 和 `grading_status` 语义保持兼容；路径更新仍返回既有 AIJob 合同，但手动更新也保留已完成任务。历史失败的 `course_builder` AIJob 仍可在任务托盘查看，前端只自动恢复非终态任务，不再强制打开旧失败弹窗。
# Phase 32 图片提问接口

- `POST /api/v1/tutor/sessions/{session_id}/attachments`：上传单张 PNG/JPEG，最大 4 MiB，返回私有附件摘要。
- `POST /api/v1/tutor/sessions/{session_id}/attachments/from-material`：把当前用户资料库中的 PNG/JPEG 图片绑定为该会话的待发送附件；只接受同用户资料，不复制或解析原图。
- `GET /api/v1/tutor/attachments/{attachment_id}/content`：当前用户鉴权读取图片内容，响应禁止缓存和 MIME sniff。
- `DELETE /api/v1/tutor/attachments/{attachment_id}`：待发送附件删除对象；已发送附件保留删除占位。
- tutor 消息请求增加 `attachment_ids`，最多 3 项；`message` 可为空，但文字和附件不能同时为空。
- `TutorMessage.attachments` 随历史、非流式响应和 SSE 完成事件返回。
- `TutorImageAttachment.material_id` 表示附件引用的持久图片资料；旧附件仍兼容原 `storage_key`。
- `POST /api/v1/settings/model/configs/{config_id}/vision-default`：设置独立图片理解默认配置；连接测试 `operation=vision` 会发送程序化无版权小图。
- 讯飞原生图片理解配置使用 `vision_app_id`、`vision_api_key`、`vision_api_secret` 写入字段；读取接口只返回是否已配置及掩码，不回传明文。连接测试必须返回完整结构化结果才判定成功。
- 模型设置的 `system_summary` 返回 `vision_model`、`vision_provider`、`vision_base_url` 与 `can_use_vision_model`，用于表示服务器级图片理解兜底；不返回服务器凭证明文或掩码。
