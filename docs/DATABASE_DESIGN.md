# EduNova 数据库设计

日期：2026-07-01

## 1. 设计目标

EduNova 数据库设计服务于学生个性化学习闭环。第一版需要同时支持内置课程、用户上传建课、RAG 检索、多智能体轨迹、学习画像、学习路径、练习评估和 Demo Mode。

设计原则：

1. 所有用户私有数据绑定 `user_id`。
2. 所有课程相关数据绑定 `course_id`。
3. 所有 AI 任务绑定 `trace_id`。
4. 生成内容必须可追溯引用来源。
5. JSON 字段用于保存灵活 AI 结构，但核心查询字段保持结构化。
6. 第一版结构为后续教师端、班级和课程包扩展预留空间。

## 2. 数据库技术

| 能力 | 技术 |
| --- | --- |
| 关系数据 | PostgreSQL |
| 向量检索 | pgvector |
| ORM | SQLAlchemy |
| 迁移 | Alembic |
| 长任务进度 | Redis |
| 文件内容 | 本地文件存储，数据库保存路径和元数据 |

## 3. 核心关系图

```mermaid
erDiagram
    users ||--o{ course_enrollments : enrolls
    users ||--o{ courses : owns
    courses ||--o{ course_materials : has
    courses ||--o{ knowledge_points : contains
    courses ||--o{ knowledge_chunks : indexes
    users ||--o{ student_profiles : has
    users ||--o{ profile_events : records
    users ||--o{ learning_paths : owns
    learning_paths ||--o{ learning_tasks : contains
    users ||--o{ generated_resources : creates
    generated_resources ||--o{ resource_quality_scores : scores
    users ||--o{ agent_run_logs : traces
    users ||--o{ practice_sessions : takes
    practice_sessions ||--o{ practice_answers : contains
    users ||--o{ assessment_reports : receives
    users ||--o{ weakness_review_queue : reviews
    users ||--o{ chat_sessions : chats
    chat_sessions ||--o{ chat_messages : contains
    users ||--o{ model_settings : configures
    users ||--o{ learning_export_jobs : exports
```

## 4. 表设计

### 4.1 `users`

用途：保存用户账号。

核心字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `email` | varchar | 邮箱，唯一 |
| `hashed_password` | varchar | 加密密码 |
| `display_name` | varchar | 显示名称 |
| `role` | varchar | `student` 或 `admin` |
| `created_at` | timestamptz | 创建时间 |
| `updated_at` | timestamptz | 更新时间 |

约束：

- `email` 唯一。
- 第一版默认 `role=student`。

### 4.2 `courses`

用途：保存内置课程和用户上传生成的课程。

核心字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `owner_id` | bigint | 创建者，内置课程可为空或指向系统用户 |
| `title` | varchar | 课程名称 |
| `description` | text | 课程说明 |
| `subject` | varchar | 学科 |
| `source_type` | varchar | `builtin`、`uploaded`、`demo` |
| `visibility` | varchar | `private`、`public` |
| `status` | varchar | `draft`、`ready`、`failed` |
| `created_at` | timestamptz | 创建时间 |

### 4.3 `course_enrollments`

用途：记录用户和课程关系。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `role` | varchar | 第一版为 `learner` |
| `progress_percent` | numeric | 进度 |
| `created_at` | timestamptz | 创建时间 |

唯一约束：

- `user_id + course_id` 唯一。

### 4.4 `course_materials`

用途：保存上传资料和解析结果。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 上传者 |
| `course_id` | bigint | 所属课程 |
| `filename` | varchar | 原文件名 |
| `content_type` | varchar | 文件类型 |
| `storage_path` | text | 文件存储路径 |
| `parse_status` | varchar | 解析状态 |
| `extracted_text` | text | 提取文本 |
| `metadata_json` | jsonb | 页码、标题、字数等元数据 |
| `created_at` | timestamptz | 创建时间 |

### 4.5 `knowledge_points`

用途：课程知识点。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `course_id` | bigint | 课程 |
| `title` | varchar | 知识点名称 |
| `summary` | text | 摘要 |
| `chapter` | varchar | 所属章节 |
| `order_index` | integer | 排序 |
| `difficulty` | varchar | 难度 |
| `prerequisites_json` | jsonb | 前置知识点 |

### 4.6 `knowledge_chunks`

用途：RAG 检索切片。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `course_id` | bigint | 课程 |
| `material_id` | bigint | 来源资料 |
| `knowledge_point_id` | bigint | 对应知识点 |
| `content` | text | 切片内容 |
| `page_number` | integer | 页码 |
| `section_title` | varchar | 小节标题 |
| `embedding` | vector | 向量 |
| `metadata_json` | jsonb | 来源元数据 |

索引：

- `course_id`。
- `knowledge_point_id`。
- `embedding` 向量索引。

### 4.7 `student_profiles`

用途：保存学生当前画像。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `profile_json` | jsonb | 8 维画像 |
| `version` | integer | 版本 |
| `updated_at` | timestamptz | 更新时间 |

### 4.8 `profile_events`

用途：记录画像变化证据链。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `dimension` | varchar | 画像维度 |
| `old_value` | text | 旧值 |
| `new_value` | text | 新值 |
| `reason` | text | 变化原因 |
| `evidence_refs` | jsonb | 证据引用 |
| `created_at` | timestamptz | 创建时间 |

### 4.9 `learning_paths`

用途：保存学习路径。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `title` | varchar | 路径标题 |
| `status` | varchar | 状态 |
| `plan_json` | jsonb | 路径结构 |
| `created_at` | timestamptz | 创建时间 |
| `updated_at` | timestamptz | 更新时间 |

### 4.10 `learning_tasks`

用途：路径中的学习任务。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `path_id` | bigint | 学习路径 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `knowledge_point_id` | bigint | 知识点 |
| `title` | varchar | 任务标题 |
| `task_type` | varchar | 讲解、练习、复习、冲刺 |
| `status` | varchar | 未开始、进行中、完成 |
| `due_at` | timestamptz | 建议完成时间 |
| `source_type` | varchar | 系统生成、评估触发、冲刺触发 |
| `evidence_refs` | jsonb | 推荐依据 |
| `order_index` | integer | 排序 |

### 4.11 `generated_resources`

用途：保存 AI 生成学习资源。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `knowledge_point_id` | bigint | 知识点 |
| `resource_type` | varchar | 资源类型 |
| `title` | varchar | 标题 |
| `content_markdown` | text | Markdown 内容 |
| `content_json` | jsonb | 结构化内容 |
| `citation_refs` | jsonb | 引用来源 |
| `review_status` | varchar | 审核状态 |
| `confidence_score` | numeric | 可信度 |
| `trace_id` | varchar | Agent 任务编号 |
| `created_at` | timestamptz | 创建时间 |

### 4.12 `resource_quality_scores`

用途：保存资源质量评分。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `resource_id` | bigint | 资源 |
| `source_match` | numeric | 资料匹配度 |
| `profile_fit` | numeric | 画像适配度 |
| `fact_confidence` | numeric | 事实可信度 |
| `difficulty_fit` | numeric | 难度适配度 |
| `completeness` | numeric | 完整度 |
| `notes` | text | 评分说明 |

### 4.13 `agent_run_logs`

用途：保存多智能体轨迹。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `trace_id` | varchar | 任务编号 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `agent_name` | varchar | Agent 名称 |
| `step_index` | integer | 步骤 |
| `input_summary` | text | 输入摘要 |
| `output_summary` | text | 输出摘要 |
| `duration_ms` | integer | 耗时 |
| `status` | varchar | 状态 |
| `citation_refs` | jsonb | 引用 |
| `review_status` | varchar | 审核状态 |
| `error_message` | text | 错误摘要 |
| `created_at` | timestamptz | 创建时间 |

索引：

- `trace_id`。
- `user_id`。
- `course_id`。

### 4.14 `practice_sessions`

用途：保存一次练习。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `title` | varchar | 练习标题 |
| `status` | varchar | 进行中、已完成 |
| `score` | numeric | 得分 |
| `started_at` | timestamptz | 开始时间 |
| `finished_at` | timestamptz | 结束时间 |

### 4.15 `practice_answers`

用途：保存每道题作答和批改。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `session_id` | bigint | 练习 |
| `user_id` | bigint | 用户 |
| `knowledge_point_id` | bigint | 知识点 |
| `question_json` | jsonb | 题目 |
| `answer_text` | text | 学生答案 |
| `is_correct` | boolean | 是否正确 |
| `score` | numeric | 单题得分 |
| `feedback` | text | 解析 |
| `created_at` | timestamptz | 创建时间 |

### 4.16 `assessment_reports`

用途：保存学习评估报告。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `report_json` | jsonb | 报告内容 |
| `mastery_json` | jsonb | 掌握度 |
| `weakness_json` | jsonb | 薄弱点 |
| `evidence_refs` | jsonb | 证据 |
| `created_at` | timestamptz | 创建时间 |

### 4.17 `weakness_review_queue`

用途：保存薄弱点复习队列。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `knowledge_point_id` | bigint | 薄弱知识点 |
| `weakness_reason` | text | 原因 |
| `priority` | integer | 优先级 |
| `recommended_resource_ids` | jsonb | 推荐资源 |
| `next_review_at` | timestamptz | 下次复习时间 |
| `status` | varchar | 待复习、进行中、完成 |

### 4.18 `chat_sessions` 与 `chat_messages`

用途：保存 AI 辅导会话。

`chat_sessions`：

- `id`。
- `user_id`。
- `course_id`。
- `title`。
- `mode`。
- `created_at`。

`chat_messages`：

- `id`。
- `session_id`。
- `user_id`。
- `role`。
- `content`。
- `citation_refs`。
- `trace_id`。
- `created_at`。

### 4.19 `model_settings`

用途：保存用户模型设置。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `provider` | varchar | 模型供应商 |
| `base_url` | text | 接口地址 |
| `encrypted_api_key` | text | 加密后的 API Key |
| `chat_model` | varchar | 聊天模型 |
| `embedding_model` | varchar | 向量模型 |
| `is_default` | boolean | 是否默认 |
| `created_at` | timestamptz | 创建时间 |

要求：

- 不保存明文 Key。
- 日志不记录 Key。
- 前端只显示脱敏 Key。

### 4.20 `learning_export_jobs`

用途：保存学习档案导出任务。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint | 主键 |
| `user_id` | bigint | 用户 |
| `course_id` | bigint | 课程 |
| `status` | varchar | 导出状态 |
| `export_type` | varchar | `markdown` |
| `output_path` | text | 输出路径 |
| `created_at` | timestamptz | 创建时间 |
| `finished_at` | timestamptz | 完成时间 |

## 5. JSON 字段约定

### 5.1 `profile_json`

```json
{
  "major_background": "",
  "knowledge_foundation": "",
  "learning_goal": "",
  "cognitive_style": "",
  "learning_preference": "",
  "weak_points": [],
  "learning_pace": "",
  "motivation_interest": ""
}
```

### 5.2 `citation_refs`

```json
[
  {
    "chunk_id": 1,
    "material_id": 1,
    "source_title": "人工智能导论讲义",
    "page_number": 12,
    "section_title": "启发式搜索",
    "content_preview": "启发式搜索利用启发函数..."
  }
]
```

### 5.3 `mastery_json`

```json
{
  "knowledge_point_id": 8,
  "status": "weak",
  "score": 0.42,
  "evidence_refs": []
}
```

## 6. 索引策略

第一版必须创建的索引：

- `users.email` 唯一索引。
- `course_enrollments(user_id, course_id)` 唯一索引。
- `courses.owner_id`。
- `course_materials(user_id, course_id)`。
- `knowledge_points(course_id)`。
- `knowledge_chunks(course_id)`。
- `knowledge_chunks(knowledge_point_id)`。
- `knowledge_chunks.embedding` 向量索引。
- `student_profiles.user_id`。
- `learning_tasks(user_id, course_id, status)`。
- `generated_resources(user_id, course_id)`。
- `agent_run_logs.trace_id`。
- `practice_sessions(user_id, course_id)`。
- `assessment_reports(user_id, course_id)`。
- `weakness_review_queue(user_id, course_id, status)`。
- `chat_sessions(user_id, course_id)`。

## 7. 数据隔离规则

所有查询必须遵守：

```text
当前用户只能访问自己拥有或已加入的课程数据。
当前用户只能访问自己的画像、路径、资源、报告、对话和导出任务。
系统内置课程可被所有用户读取，但用户学习记录仍然私有。
```

接口层和服务层都应校验访问权限。不能只依赖前端隐藏入口。

## 8. Demo 数据规则

Demo Mode 数据使用固定演示账号：

```text
demo@edunova.local
```

Demo 数据要求：

- 可重置。
- 与真实用户数据隔离。
- fallback 资源明确标记。
- 不使用真实个人隐私数据。

## 9. 迁移策略

使用 Alembic 管理数据库变更。

规则：

1. 每次修改模型后生成迁移脚本。
2. 迁移脚本进入 Git。
3. 不能手动要求用户在数据库执行未记录 SQL。
4. 表和字段命名保持小写下划线。
5. 删除字段前先确认没有业务依赖。

## 10. 数据库验收标准

第一版数据库达到以下标准才算可用：

1. 所有核心表可通过迁移创建。
2. 内置人工智能导论课程可导入。
3. 上传资料能写入课程、材料、知识点和知识切片。
4. RAG 检索能读取向量数据。
5. 资源、报告、对话都能追溯用户、课程和 trace。
6. 两个不同用户的数据互不可见。
7. Demo 数据可重置且不污染普通用户数据。
