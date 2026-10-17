# EduNova 数据库设计

数据层使用 PostgreSQL、SQLAlchemy、Alembic 和 pgvector。本文说明数据域与约束，列定义以 `backend/app/models/` 和迁移为准。

## 1. 数据域

| 数据域 | 主要表 |
| --- | --- |
| 账号与课程 | `users`、`courses`、`course_enrollments` |
| 资料库 | `materials`、`material_chunks`、`course_material_links`、`material_comparison_runs` |
| 课程知识 | `course_materials`、`knowledge_points`、`knowledge_chunks` |
| 向量归档 | `chunk_embedding_archives` |
| 学习画像 | `student_profiles`、`profile_events` |
| 路径与弱点 | `learning_paths`、`learning_tasks`、`weakness_review_queue` |
| 学习资源 | `generated_resources`、`resource_interactions`、`resource_quality_scores` |
| 练习与报告 | `practice_sessions`、`practice_answers`、`assessment_reports` |
| 会话与记忆 | `chat_sessions`、`chat_messages`、`chat_message_attachments`、`conversation_memory_entries` |
| 长期信息与删除屏障 | `learning_memory_facts`、`memory_suppressions` |
| 任务与审计 | `ai_jobs`、`export_jobs`、`agent_run_logs`、`model_call_runs` |
| 设置与隐私 | `model_settings`、`user_privacy_settings` |

## 2. 所有权与隔离

用户数据须能追溯到 `user_id`。课程查询同时验证所有权或 enrollment，资源 ID 本身不代表访问权限。

关键规则：

- 个人资料库中的原文件属于上传用户；
- 资料通过 `course_material_links` 加入课程，不改变原文件所有权；
- 课程知识点、切片、路径、资源、练习和报告按课程隔离；
- A 课程的画像证据、弱点和资源反馈不能进入 B 课程；
- 删除账号或课程时按模型定义执行级联或置空，不遗留可被其他用户访问的数据。

## 3. 资料与课程证据

`materials` 保存资料元数据、解析状态与版本化目录，`material_chunks` 保存章节切片。建课后，`course_materials` 保存兼容课程来源，`knowledge_chunks` 保存检索切片。

引用只保存必要的资料、章节、页码、切片和检索状态。完整原文保留在受控文件或切片记录中，不复制到日志和 Trace。

`20260923_0037` 增加向量归档。每条只关联课程或资料切片之一，由切片 ID、内容摘要、模型 profile 唯一定位，保留模型、维度、向量与原生成时间。显式重建在同一批事务中归档旧向量、更新当前向量，锁定切片及所有者；模型调用在锁外执行。同内容/profile 可恢复历史向量。归档随切片删除，非空时禁止降级删表。普通检索不覆盖有效向量，仅使用当前 profile 的候选。

## 4. 学习状态

`20260914_0035` 为 `learning_paths` 增加 `approval_status` 和 `approved_at`。旧记录保持 `legacy`、空确认时间，保留 `plan_json`、任务状态和成绩。新草稿为 `status=draft`；批准后变为 active/approved，旧 active 路径归档。批准与生成提交共用课程行锁，核对基础路径 ID 以防并发覆盖；模型调用在锁外执行。

迁移前备份数据库、停止旧 worker 写入，使用 Alembic 升级。仅在全部记录仍为 legacy 时允许降级删除新列；已有草稿或批准信息则拒绝，应前向修复，保留用户确认。隔离 PostgreSQL 回归覆盖旧 JSON、升级/降级/再升级及并发批准。

`student_profiles` 保存可复用画像，`profile_events` 保存经过约束的画像证据。课程目标、课程基础、弱点、掌握度和路径通过 enrollment 与课程级表表达。

`20260914_0036` 为 `resource_interactions` 增加非空 JSONB `evidence_json`，旧行默认为空对象，不追认历史来源。存在非空证据时拒绝降级删列，需备份并前向修复。隔离 PostgreSQL 检查升级、旧行默认值、降级/再升级及证据保留。

任务复用 `learning_bundle_json.items` 的固定资源 ID，增加 binding 快照（版本族/序号、内容与引用摘要）和 `binding_contract=1`；资源、任务和交互外键不变。生成提交锁定任务，只填空槽，不覆盖版本；活动创建锁定资源，串行化重复 event_id；批准使用课程行锁。

绑定测验通过任务行锁保证同任务/资源只创建一个 PracticeSession。`assessment_json.source_binding` 与 `PracticeAnswer.question_json.source_binding` 保存同一来源，原题引用和答案随快照保存。评分沿用 AssessmentGraph、提交认领与事务，不从阅读推断掌握；归档计划的测验不自动切换版本。

掌握度和报告中的确定性数字由练习、任务和资源互动记录计算，不把模型自然语言直接当作正式评分。

## 5. 资源版本

`generated_resources` 使用版本族和版本号保留生成历史。新版本不会覆盖旧版本；替代和优化操作记录直接来源。资源内容和引用使用版本化 JSON 合同，读取旧记录时采用兼容默认值。

## 6. 后台任务

`ai_jobs` 与 `export_jobs` 保存任务状态、工作流、输入摘要、结果引用、错误码和恢复信息。任务正文与大型文件不放入 Redis；Redis 只承担排队和运行协调。

## 7. 会话与隐私

`chat_messages` 保存用户和助手消息，引用保存在 `citation_json`。附件通过 `chat_message_attachments` 记录逻辑键和安全元数据，实际文件由存储适配器管理。

跨会话记忆由用户控制：暂停保留内容与索引，清除索引保留摘要，永久删除移除相应内容并阻断旧来源恢复；各项均保留原始会话。

## 8. 模型设置

用户模型配置按用户隔离。API Key 使用应用级加密密钥加密保存；接口只返回配置来源、模型、可用性和脱敏后的 Key 状态。

数据库备份必须与 `MODEL_SETTINGS_ENCRYPTION_KEY` 分开保管。没有对应加密密钥的备份不能恢复用户模型凭据。

模型调用审计由 `20260925_0038` 增加可空 `usage_json` 和 `session_id`；旧值保持为空，不反推历史费用。用量仅包含每次尝试的计数、状态、耗时及可选报价快照，沿用 `MODEL_CALL_LOG_RETENTION_DAYS`。升级先运行 Alembic 再启动新 worker；降级删除新增字段，须先备份审计数据，原始聊天不受影响。

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

## 11. 任务证据投影与恢复

运行历史用 `ai_jobs.progress_json.snapshot` 保存一次终态元数据，不新增表或迁移。快照整体替换持久化，包含 schema_version、任务/Trace/父运行身份、产物引用、输入及路径内容 SHA256、脱敏步骤、用量和整体摘要。捕获锁定 Job，重复捕获保留原值。摘要只检查一致性，不防数据库管理员篡改；快照随 Job 删除，不是永久审计存档。

Session 沿用领域会话与 AIJob 身份；快照不序列化 ORM、模型上下文或成绩。回放只读，不修复 Job 或写入领域事实。

计划分支在课程行锁内核对当前路径 ID 与源内容摘要，以 `plan_json.branch_snapshot` 保证并发幂等。新版本为 draft，记录 revision_of/branched_from，复制任务蓝图及固定资源引用、重置状态，不复制交互、练习、评分或掌握事实。

重新执行沿用队列、幂等键与权限门禁，在 progress_json 记录 reexecuted_from/source_snapshot，retry_of_job_id 为空。旧任务仍可读，可显式捕获终态元数据，不补造批准或学习证据。

任务进度只读聚合已批准 `learning_paths`、`learning_tasks.learning_bundle_json` 资源快照、`resource_interactions.evidence_json`、`practice_sessions.assessment_json.source_binding` 和既有掌握度，不新增前端可写的掌握度。历史 `learning_tasks.status=completed` 仍是用户报告；资源活动与评估来源不匹配时不能闭合任务。

路径/资源与 AIJob 状态分别提交。提交后取消或超时保留产物，回写记录原引用；worker 中断时，显式重试按原 `agent_trace_id` 查找同用户、同课程产物。恢复需核验状态与绑定，不替换版本或重评；无已提交产物才重新执行，冲突需新请求。其他工作流保留各自恢复策略，不提供通用快照、分支或重放引擎。

## 12. 受控记忆增量（20260925_0039）

`user_privacy_settings` 增加 `memory_revision` 和 `memory_cleared_before`，阻断隐私操作前的排队/在途写入及清空前来源。`conversation_memory_entries` 保留消息外键，增加主题、更新时间和纠正版本；向量可空，区分保留摘要与可用索引。

`learning_memory_facts` 按账号保存用户确认的类别、文本、版本和时间，不从评分或助手回答自动生成。`memory_suppressions` 只保存账号及来源助手消息 ID，不留已删正文，随来源级联删除。记忆写入、纠正、隐私控制与删除共用账号行锁；向量计算在锁外，提交前复核隐私版本与来源屏障。

升级不删除原聊天或已有记忆；有长期信息、删除标记或隐私版本变更时拒绝直接降级，防止旧代码恢复已删除内容。迁移兼容性、阈值隔离及后台并发删除由 `backend.integration.memory_control_check` 在隔离数据库验证。
