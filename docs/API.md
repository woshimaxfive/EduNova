# EduNova API 设计

日期：2026-07-01

## 1. 设计目标

本文档定义 EduNova 第一版前后端接口约定。接口设计以学生学习主链路为中心，兼顾 Demo Mode、RAG 引用、多智能体轨迹和后续开源部署。

接口基础路径：

```text
/api/v1
```

健康检查路径：

```text
/api/health
```

## 2. 通用约定

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
  "display_name": "小新"
}
```

响应：

```json
{
  "data": {
    "id": 1,
    "email": "student@example.com",
    "display_name": "小新",
    "role": "student"
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
      "role": "student"
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
    "role": "student"
  },
  "trace_id": "trace_20260701_003"
}
```

### POST `/auth/logout`

用途：退出登录。第一版前端清理 token，后端返回成功。

## 5. Dashboard 接口

### GET `/dashboard/summary`

用途：获取学生工作台总览。

响应包含：

- 画像摘要。
- 当前课程。
- 今日任务。
- 最近资源。
- 薄弱点。
- Agent 轨迹。

响应示例：

```json
{
  "data": {
    "profile_summary": {
      "knowledge_foundation": "机器学习入门",
      "learning_goal": "期末前掌握神经网络"
    },
    "current_course": {
      "id": 1,
      "title": "人工智能导论",
      "progress_percent": 35
    },
    "today_tasks": [],
    "recent_resources": [],
    "weak_points": [],
    "latest_agent_logs": []
  },
  "trace_id": "trace_20260701_004"
}
```

## 6. Profile 接口

### GET `/profiles/me`

用途：读取当前学生画像。

响应：

```json
{
  "data": {
    "id": 1,
    "version": 3,
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
    "updated_at": "2026-07-01T10:30:00+08:00"
  },
  "trace_id": "trace_20260701_005"
}
```

### POST `/profiles/chat`

用途：通过对话更新学习画像。

请求：

```json
{
  "message": "我是计算机专业大二学生，机器学习刚入门，数学基础一般，想期末前掌握神经网络。"
}
```

响应包含 AI 回复、画像变更和事件。

### GET `/profiles/events`

用途：查看画像变化记录。

## 7. Course 接口

### GET `/courses`

用途：获取我的课程列表。

查询参数：

- `source_type`：`builtin`、`uploaded`。

### GET `/courses/{course_id}`

用途：获取课程详情。

### GET `/courses/{course_id}/overview`

用途：获取课程概览、章节和知识点。

### GET `/courses/{course_id}/knowledge-points`

用途：获取课程知识点。

### GET `/courses/{course_id}/mastery-map`

用途：获取知识点掌握地图。

响应包含：

- 知识点。
- 掌握状态。
- 先修关系。
- 推荐复习标记。

## 8. Materials 接口

### POST `/materials/upload`

用途：上传课程资料。

请求类型：`multipart/form-data`

字段：

- `course_id`：可选，不传时可创建新课程。
- `file`：上传文件。

支持类型：

- PDF。
- PPTX。
- DOCX。
- Markdown。
- TXT。

响应：

```json
{
  "data": {
    "material_id": 1,
    "course_id": 1,
    "filename": "ai-notes.md",
    "parse_status": "uploaded"
  },
  "trace_id": "trace_20260701_006"
}
```

### GET `/materials/{material_id}`

用途：查看资料详情。

### GET `/materials/{material_id}/progress`

用途：查看资料解析和建课进度。

响应：

```json
{
  "data": {
    "status": "chunking",
    "progress_percent": 60,
    "message": "正在切分知识片段"
  },
  "trace_id": "trace_20260701_007"
}
```

### POST `/courses/from-materials`

用途：根据一个或多个资料生成课程。

请求：

```json
{
  "material_ids": [1, 2],
  "course_title": "机器学习期末复习"
}
```

### POST `/materials/compare`

用途：对比多份资料并提炼考点。

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

用途：检索课程知识库。

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
        "score": 0.88
      }
    ]
  },
  "trace_id": "trace_20260701_008"
}
```

## 10. Resource 接口

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

用途：创建辅导会话。

请求：

```json
{
  "course_id": 1,
  "mode": "socratic",
  "title": "反向传播答疑"
}
```

### GET `/tutor/sessions`

用途：查看会话列表。

### GET `/tutor/sessions/{session_id}`

用途：查看会话详情。

### POST `/tutor/sessions/{session_id}/messages`

用途：发送问题并获取回答。

请求：

```json
{
  "message": "为什么反向传播要用链式法则？"
}
```

响应包含回答、引用、低依据标记和 trace_id。

### GET `/tutor/sessions/{session_id}/stream`

用途：SSE 流式返回回答。第一版可在普通接口稳定后接入。

## 14. Practice 与 Report 接口

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

用途：获取当前模型设置。

### PUT `/settings/model`

用途：保存模型设置。

请求：

```json
{
  "provider": "openai_compatible",
  "base_url": "https://api.example.com/v1",
  "api_key": "example-key",
  "chat_model": "example-chat-model",
  "embedding_model": "example-embedding-model"
}
```

响应不返回明文 API Key，只返回脱敏结果。

### POST `/settings/model/test`

用途：测试模型连通性。

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
