# EduNova 数据库设计

EduNova 使用 PostgreSQL、SQLAlchemy、Alembic 和 pgvector。本文档说明当前数据域和约束，具体列定义以 `backend/app/models/` 和迁移文件为准。

## 1. 数据域

| 数据域 | 主要表 |
| --- | --- |
| 账号与课程 | `users`、`courses`、`course_enrollments` |
| 资料库 | `materials`、`material_chunks`、`course_material_links`、`material_comparison_runs` |
| 课程知识 | `course_materials`、`knowledge_points`、`knowledge_chunks` |
| 学习画像 | `student_profiles`、`profile_events` |
| 路径与弱点 | `learning_paths`、`learning_tasks`、`weakness_review_queue` |
| 学习资源 | `generated_resources`、`resource_interactions`、`resource_quality_scores` |
| 练习与报告 | `practice_sessions`、`practice_answers`、`assessment_reports` |
| 会话与记忆 | `chat_sessions`、`chat_messages`、`chat_message_attachments`、`conversation_memory_entries` |
| 任务与审计 | `ai_jobs`、`export_jobs`、`agent_run_logs`、`model_call_runs` |
| 设置与隐私 | `model_settings`、`user_privacy_settings` |

## 2. 所有权与隔离

用户级数据必须能够追溯到 `user_id`。课程相关查询同时验证课程所有权或 enrollment，不接受仅凭资源 ID 的访问。

关键规则：

- 个人资料库中的原文件属于上传用户；
- 资料通过 `course_material_links` 加入课程，不改变原文件所有权；
- 课程知识点、切片、路径、资源、练习和报告按课程隔离；
- A 课程的画像证据、弱点和资源反馈不能进入 B 课程；
- 删除账号或课程时按模型定义执行级联或置空，不遗留可被其他用户访问的数据。

## 3. 资料与课程证据

`materials` 保存原始资料元数据、解析状态和版本化目录；章节切片保存在 `material_chunks`。课程建立后，兼容课程来源保存在 `course_materials`，检索切片保存在 `knowledge_chunks`。

引用只保存必要的资料、章节、页码、切片和检索状态。完整原文保留在受控文件或切片记录中，不复制到日志和 Trace。

## 4. 学习状态

`student_profiles` 保存可复用画像，`profile_events` 保存经过约束的画像证据。课程目标、课程基础、弱点、掌握度和路径通过 enrollment 与课程级表表达。

掌握度和报告中的确定性数字由练习、任务和资源互动记录计算，不把模型自然语言直接当作正式评分。

## 5. 资源版本

`generated_resources` 使用版本族和版本号保留生成历史。新版本不会覆盖旧版本；替代和优化操作记录直接来源。资源内容和引用使用版本化 JSON 合同，读取旧记录时采用兼容默认值。

## 6. 后台任务

`ai_jobs` 与 `export_jobs` 保存任务状态、工作流、输入摘要、结果引用、错误码和恢复信息。任务正文与大型文件不放入 Redis；Redis 只承担排队和运行协调。

## 7. 会话与隐私

`chat_messages` 保存用户和助手消息，引用保存在 `citation_json`。附件通过 `chat_message_attachments` 记录逻辑键和安全元数据，实际文件由存储适配器管理。

跨会话记忆为用户可控的派生数据。关闭或清除记忆不会删除原始会话，但必须删除相应派生索引。

## 8. 模型设置

用户模型配置按用户隔离。API Key 使用应用级加密密钥加密保存；接口只返回配置来源、模型、可用性和脱敏后的 Key 状态。

数据库备份必须与 `MODEL_SETTINGS_ENCRYPTION_KEY` 分开保管。没有对应加密密钥的备份不能恢复用户模型凭据。

## 9. 迁移

迁移文件位于 `backend/migrations/versions/`。升级时只使用 Alembic：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic heads
```

当前仓库要求单一 migration head。不要手工修改生产表来绕过迁移，也不要删除已经发布的迁移文件。

## 10. 备份范围

可恢复备份至少包括：

- PostgreSQL 数据库；
- 上传资料和聊天附件；
- 导出文件（如果需要长期保留）；
- 部署配置和独立保存的加密密钥。

Redis 队列不是唯一事实来源，可以在数据库与文件恢复后重新建立运行状态。
