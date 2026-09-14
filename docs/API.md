# EduNova API

EduNova 后端使用 FastAPI，默认 API 前缀为 `/api/v1`。机器可读合同以 `backend/openapi.json` 为准。

### 计划草稿与批准

- `POST /paths/generation-jobs` 传 `{"course_id":101,"draft":true}` 生成待确认草稿；从 Job 结果的 `path_id` 查询具体版本。
- `GET /paths/drafts?course_id=101` 列出最近 50 个待确认草稿；`GET /paths/{path_id}` 读取该版本及任务，含历史版本。
- `POST /paths/{path_id}/approve` 必须传 `expected_active_path_id`（首次无当前计划时显式传 `null`）。该值必须与草稿的 `plan_json.revision_of` 和当前生效计划一致，否则返回 409。重复批准同一仍生效的版本保持幂等。
- 计划返回 `approval_status`（`legacy`、`draft`、`approved`）与 `approved_at`。路径 ID 是版本身份，`schema_version` 只是结构版本，不能当批准记录。
- 草稿不改变 `/paths/current`，不能更新任务进度、生成任务资源或记录任务活动；批准后才激活。已批准计划后续重规划只生成草稿，原计划继续生效。
- 为兼容现有客户端，未指定 `draft` 且没有已批准当前计划时仍走旧生成模式，明确标记 `legacy`，不伪装为已批准。当前前端尚未接入新批准入口；可通过 API 验收。

批准不表示评估通过或已掌握。任务资源与评估的来源合同如下；学习闭环的掌握判定仍由原服务端流程负责。

### 任务、资源与评估来源

- `GET /paths/tasks/{task_id}` 读取任务所属计划版本，包含已归档版本；草稿任务不可执行。工作台使用此接口，不把旧任务替换为当前计划任务。
- `learning_bundle.items` 返回 `binding_status` 和 `resource_version`。新绑定记录固定资源 ID、版本族/序号以及内容和引用的 SHA-256；只有审核 passed 且快照匹配的资源才为 verified。旧明确关联保留 legacy_unverified；无 ID 的旧推荐不猜补。缺失、越权、未审核和快照冲突不返回可打开的资源 ID。
- 已绑定版本不被生成请求覆盖，缺失时返回冲突并要求新计划版本。可为尚未绑定的槽位生成资源，保存时锁定任务、复核并绑定；禁止删除带验证快照的任务来源资源。课程/账号隐私删除仍遵循既有级联规则。
- `POST /paths/tasks/{task_id}/resources/{resource_id}/practice` 从已批准计划的 verified quiz 创建练习，不重新生成原题；校验原题 ID、选项/答案和课程引用，返回既有 PracticeSessionDetail。相同任务/资源的并发或重复请求返回同一 session；使用原 `/practice/sessions/{session_id}/submit` 提交接口评分。
- 练习响应 `source_binding` 和持久化原题保留计划、任务、资源快照与评分合同。该资源原本可查看参考答案，因此来源记录明确包含答案可见性，不作为独立盲测证明。旧练习不补造来源。
- `GET /resources/{resource_id}/learning-state?path_task_id=...` 读取该任务的活动状态；省略任务参数只读取独立资源活动。返回的 evidence 保存活动来源快照；历史空证据标记 legacy_unverified。相同 event_id 必须对应同一任务、资源和事件内容；阅读/手动完成活动不改变掌握度，也不自动完成路径任务。

## 1. 在线文档

启动服务后可访问：

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`
- 健康检查：`GET /api/health`

通过 `scripts/check_openapi.py` 检查已提交 OpenAPI 与当前后端是否一致。重新生成合同和前端传输类型：

```powershell
pnpm --dir frontend openapi:generate
```

## 2. 鉴权

除注册、登录和健康检查外，业务接口通常要求：

```http
Authorization: Bearer <access-token>
```

客户端只能访问当前账号拥有或加入的课程、资料、会话、任务和产物。不要在 URL、日志或错误报告中传递访问令牌。

## 3. 接口分组

| 分组 | 前缀 | 用途 |
| --- | --- | --- |
| Auth | `/api/v1/auth` | 注册、登录、当前账号 |
| Dashboard | `/api/v1/dashboard` | 学习主页摘要 |
| Materials | `/api/v1/materials` | 上传、目录确认、资料库与资料对比 |
| Courses | `/api/v1/courses` | 课程、知识点、建课和课程状态 |
| RAG | `/api/v1/rag` | 课程证据检索 |
| Tutor | `/api/v1/tutor` | 主页与课程辅导会话、SSE 回答 |
| Profiles | `/api/v1/profiles` | 学习画像和画像证据 |
| Learning | `/api/v1/learning` | 下一行动和学习状态 |
| Paths | `/api/v1/paths` | 学习路径和任务 |
| Resources | `/api/v1/resources` | 资源生成、版本、反馈和质量 |
| Practice | `/api/v1/practice` | 练习、作答和评估 |
| Reports | `/api/v1/reports` | 学习报告 |
| Exports | `/api/v1/exports` | 文档、课件和报告导出 |
| AI Jobs | `/api/v1/ai-jobs` | 后台任务查询、事件、取消和重试 |
| Agents | `/api/v1/agents` | 安全协作摘要和 Trace |
| Settings | `/api/v1/settings` | 模型、隐私和功能配置 |
| Speech | `/api/v1/speech` | 语音识别与朗读 |

具体路径、参数、状态码和 Schema 请在 Swagger UI 或 OpenAPI JSON 中查询，避免复制一份容易漂移的手写合同。

## 4. 流式响应

辅导回答和后台任务使用符合 SSE 规范的事件流。客户端应使用事件解析器处理分包，不应按换行手工拼接 JSON。

事件只包含学生可见内容、进度、引用和安全元数据，不包含模型原始推理或完整输入。

## 5. 后台任务

资料解析、智能建课、资源生成、路径规划、练习生成、报告生成和导出可能返回后台任务。典型流程：

```text
创建任务 → 保存 job_id → 查询或订阅进度 → 获取完成结果
                         ↘ 取消 / 安全重试
```

客户端应把 `job_id` 作为恢复依据，并处理 `queued`、`running`、`cancelling`、`completed`、`failed` 和 `cancelled` 等状态。

## 6. 错误处理

业务错误通过统一错误合同返回。调用方应根据 HTTP 状态码和业务错误码处理，不要依赖自然语言错误文本。

常见类别包括：

- 401：未登录或令牌失效；
- 403：没有资源访问权限；
- 404：资源不存在或对当前用户不可见；
- 409：状态冲突、目录未确认或重复操作；
- 422：请求不符合 Schema；
- 429：调用或任务并发受限；
- 5xx：服务或外部依赖异常。

练习正式交卷还定义稳定错误码：`DUPLICATE_QUESTION_ID`（重复题号，400）、`INCOMPLETE_SUBMISSION`（缺题或混入未知题，422）和 `PRACTICE_ALREADY_COMPLETED`（已完成会话再次交卷，409）。

## 7. 兼容性

- `/api/v1` 是当前公共 API 版本前缀。
- OpenAPI 是前后端传输合同的事实来源。
- 数据库 JSON 字段读取时保留安全默认值，以兼容旧记录。
- 删除或改变公共字段前应提供迁移和前端兼容期。

## 8. 练习提交与草稿版本

- `PATCH /api/v1/practice/sessions/{session_id}/draft` 是草稿保存接口，允许只保存部分题目；请求必须携带递增的 `revision`。服务端只接受高于当前版本的草稿，旧版本返回 `409`，防止网络乱序覆盖新输入。
- `POST /api/v1/practice/sessions/{session_id}/answers` 是正式交卷接口，提交题目集合必须与当前练习完全一致，不能缺题、增加未知题或重复题号。
- 每个答案可带 `answered`：`false` 明确表示未作答；旧客户端的 `"未作答"` 会兼容转换。未作答按 0 分计入总分，但不会被当作知识性错误写入弱点诊断。
- `PracticeAnswer.question_id` 与 `(session_id, question_id)` 唯一约束是提交和重评的权威身份；不再依赖题目 JSON 内嵌 ID。
- 选择题返回稳定 `option_ids`（`A`、`B`…）；客户端应提交选项 ID。服务端仍接受旧版文本答案，以便历史草稿过渡。
- 多选题要求用户答案集合与标准答案集合严格相等；多选错选不会被判为满分。
- 练习完成后再次正式提交返回 `409`，不会覆盖原成绩或答案；简答题需要重新评分时使用 `/regrade`。
- AI 任务重试只有在新任务成功创建后才消耗原任务的重试次数；输入校验失败不消耗额度。

## 9. 检索、存储与取消边界

- embedding 和 rerank 是系统级检索基础设施：用户模型配置不能成为其默认路由；`/model/embedding/reindex-jobs` 只使用当前系统向量配置，`config_id` 仅为兼容字段。
- 上传资料、图片附件和导出文件先写入临时对象键；数据库提交后才提升为正式对象键。提升失败会保留可追踪的 `pending_promotion` 状态和临时键，供任务重试或巡检恢复。
- AI 任务在启动、工作流返回和向量批次落盘前检查取消请求；取消任务不能再被标为 `completed`。

对于路径规划和资源生成，领域提交完成后到达的取消/超时不会撤销已保存产物。任务结果可携带 `domain_committed: true` 与原产物 ID；显式重试先验证原请求、归属和绑定，再复用产物。worker 未写回任务结果便中断时，重试按原 Trace 查找已提交产物；存在冲突则阻断，不自动选取其他版本。部分资源批次只恢复已保存资源，缺失类型仍列为失败。其他工作流沿用各自恢复合同。

## 10. 任务证据进度

`GET /api/v1/paths/tasks/{task_id}/progress` 只读返回指定任务版本的四个独立维度：

| 字段 | 依据 |
|---|---|
| `user_reported_completed` | 兼容旧任务完成标记，属于用户报告 |
| `activity_completed` | 已批准版本的所有 bundle 项均有验证一致的活动；测验须有已提交的绑定评估 |
| `assessment_passed` | 所有必需测验有同任务、同路径、同资源快照的完整服务端评分，得分至少 80；没有测验则为 false |
| `mastered` | 直接复用课程知识点掌握度规则，包括有效答题证据与薄弱点状态，不由任务标记推断 |

返回值还包括活动数量、事件/评估 ID、掌握分、阻断原因、`rule_version` 和 `next_step`。`study_resource`、`take_assessment`、`review_assessment` 指向精确资源；缺失、未审核或版本冲突返回 `resolve_binding`。阅读反馈仍是用户自述，服务端核验其身份与版本不等于证明学习效果。旧计划不补造批准或评估证据。

已批准计划的下一行动依据上述证据推进。工坊的任务资源显示四维状态，绑定 quiz 可进入既有练习页。重新打开已提交测验复用原会话，正式重复提交返回 409；读取进度、成绩和轨迹不会再次调用模型或增加评分。全新计划编辑/批准工作台另行提供。

## 11. 能力目录与运行历史

`GET /api/v1/agents/capabilities` 需要登录，描述实际适配的输入/输出合同、Provider 协议、搜索工具范围及允许的历史操作。七类 AIJob 均在入队和执行前校验类型与权限，执行后验证结果；沿用现有超时、取消、预算、Trace 和失败分类。课程生成的结果课程 ID 仍为字符串，未产生向量时仍不返回 Provider/模型字段。

辅导对话、画像、正式交卷及资料对照继续使用原领域 API/Pydantic 合同和只读 Trace，不进入第二套队列，也不支持通用分支或重新执行。目录中的 Provider 标记是适配器协议声明（`adapter_contract_not_live_probe`），不是当前账号连接成功证明；个人模型结构化输出/视觉仍需原连接测试与执行门禁。搜索工具使用既有 LangChain ToolNode 和严格参数合同，失败返回警告而非虚构引用，不能写掌握度。

| 操作 | 合同 |
|---|---|
| `POST /ai-jobs/{id}/snapshot` | 仅终态任务；首次保存后幂等返回。保存脱敏步骤、计数、产物 ID、输入摘要及校验摘要，不保存原始 Prompt、答案或密钥 |
| `GET /ai-jobs/{id}/replay` | 只读返回已保存快照；不存在为 404，校验失败为 409。不运行模型、工具、评分，也不做过期任务状态修复 |
| `POST /ai-jobs/{id}/branch` | 请求 `expected_digest` 和必填可空 `expected_active_path_id`；仅有可验证路径产物的快照支持。创建未批准草稿、任务均为 todo，保持当前计划，禁止复制学习事件和成绩；同一快照并发创建复用同一分支 |
| `POST /ai-jobs/{id}/reexecute` | 请求 `expected_digest` 和必填 `Idempotency-Key`；创建关联源快照的新 AIJob。路径强制草稿，资源仅允许原请求未绑定任务的情况；其他能力明确返回 409，请使用其领域入口 |

表中路径均以 `/api/v1` 为前缀，全部按用户隔离。源路径内容/资源绑定或当前基础版本变化时拒绝首次分支；摘要不匹配拒绝重新执行。同一重新执行键复用一个新任务，不消耗旧任务重试次数；不同键是明确的新请求，仍受权限、并发和预算限制。`retry` 是原有失败恢复入口，不等于 `reexecute`。

这些接口提供运行历史基础；全新工作台界面另行提供。快照不是可恢复的模型上下文，也不能覆盖领域数据库事实。
