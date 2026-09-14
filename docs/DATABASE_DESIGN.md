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

`20260914_0035` 为 `learning_paths` 增加 `approval_status` 与 `approved_at`。旧记录保留 `legacy`、确认时间为空，不修改 `plan_json`、任务状态或历史成绩。新增草稿使用 `status=draft`；批准后变为 active/approved，旧 active 路径归档。批准与路径生成的持久化阶段锁定同一课程行，并核对基础路径 ID，避免两个确认或生成覆盖当前版本；模型调用期间不持有这把锁。

迁移前需备份数据库并停止旧版本 worker 写入。升级采用 Alembic 正常版本追踪。降级仅在所有记录仍是 legacy 时允许删除新列；已有草稿或批准信息时主动拒绝降级，应保留数据做前向修复，不能为回滚应用而抹除用户确认。隔离 PostgreSQL 回归覆盖旧 JSON 保留、升级—降级—再升级及双会话竞争批准。

`student_profiles` 保存可复用画像，`profile_events` 保存经过约束的画像证据。课程目标、课程基础、弱点、掌握度和路径通过 enrollment 与课程级表表达。

`20260914_0036` 为 `resource_interactions` 添加非空 JSONB `evidence_json`，旧行默认空对象，禁止追认历史精确来源。有非空证据时降级拒绝删除该列，应备份并前向修复。隔离 PostgreSQL 检查升级、旧行默认值、降级/再升级和拒绝丢证据。

任务继续复用 `learning_bundle_json.items` 的固定资源 ID，新增 binding 快照（版本族/序号、内容与引用摘要）和 `binding_contract=1`。没有引入平行版本系统；原资源、任务和交互外键保持不变。生成提交锁定任务行，仅填充空槽，不覆盖已有版本。活动创建锁定资源行以串行化重复 event_id；批准仍使用课程行锁。

绑定测验通过任务行锁保证相同任务/资源只创建一个 PracticeSession。`assessment_json.source_binding` 与 `PracticeAnswer.question_json.source_binding` 保存相同来源，原题引用和答案随题目快照保存；后续评分继续使用既有 AssessmentGraph、提交认领和事务，不直接从资源阅读推断掌握。已归档计划的既有测验不自动切换到新版本。

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

## 11. 任务证据投影与恢复

运行历史扩展复用 `ai_jobs.progress_json.snapshot` 保存一次终态元数据，不新增数据库表或迁移。快照以整个 JSON 值替换持久化，包含 schema_version、任务/Trace/父运行身份、产物引用、输入及路径内容 SHA256、脱敏步骤、用量计数和整体摘要。捕获时锁定 Job 行，重复捕获保持原值；摘要用于一致性检测，不是防数据库管理员篡改的签名。删除 Job 会一并删除其快照，不宣称永久审计存档。

Session 沿用领域会话与 AIJob 执行身份；快照不序列化 ORM 对象、模型上下文或成绩。读取重放不修复 Job 状态，不写领域事实。计划分支在课程行锁内检查当前路径 ID 和源内容摘要，以 `plan_json.branch_snapshot` 实现并发幂等，创建 draft、记录 revision_of/branched_from，复制任务蓝图及固定资源引用但重置任务状态；不复制交互、练习、评分或掌握事实。新执行使用原队列、幂等键和权限门禁，在 progress_json 记录 reexecuted_from/source_snapshot，retry_of_job_id 保持空值。旧任务没有快照仍可读，可显式捕获终态元数据，不能补造历史批准或学习证据。

任务进度由已批准 `learning_paths`、`learning_tasks.learning_bundle_json` 的资源快照、`resource_interactions.evidence_json`、`practice_sessions.assessment_json.source_binding` 与既有掌握度计算只读聚合，不新增可被前端直接写入的掌握度字段。历史 `learning_tasks.status=completed` 仍保留用户报告语义。资源活动与评估来源不匹配时不能闭合任务。

路径/资源的领域事务与 AIJob 状态事务保持分离。提交后取消或超时保留产物，任务回写中记录原结果引用；worker 中断缺少回写时，显式重试使用原 `agent_trace_id` 查询同用户、同课程的领域产物。恢复验证状态与绑定，不替换原版本、不重新评分；没有已提交产物才重新执行，冲突需要用户明确创建新请求。本机制不替代其他工作流自己的恢复策略，也不提供通用快照、分支或重放引擎。
