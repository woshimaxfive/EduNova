# EduNova API

EduNova 后端使用 FastAPI，默认 API 前缀为 `/api/v1`。机器可读合同以 `backend/openapi.json` 为准。

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

完整路径、参数、状态码与 Schema 见 Swagger UI 或 OpenAPI JSON；下文说明跨接口约束。

## 4. 流式响应

辅导回答和后台任务使用符合 SSE 规范的事件流。客户端应使用事件解析器处理分包，不应按换行手工拼接 JSON。

首页与课程辅导检测到取消时可发送 `cancelled` 终止事件，含 `message`。客户端停止消费，以 `ANSWER_CANCELLED` 展示结果，不等待 `done` 或记为成功。此事件不新增取消入口，也不保证立即中断已发送的同步模型请求。

课程辅导的 `status` 阶段为 `answer_receiving`（接收正文）、`answer_checking`（安全与依据核对）、必要时 `answer_repairing`（修订无依据表述）。状态不含未审核正文、不写入聊天；`token` 仍在整答核对后发送。阶段反馈不代表首字提速或回答成功。

普通定义与基础概念对照默认简洁回答；详细讲解、推导和代码按需展开，不仅因“比较”等措辞启用深度模式，用户显式选择仍生效。检索片段按需引用，不逐一展开。篇幅指导不硬截断，安全核对、依据不足提示与必要前提保留。

事件只包含学生可见内容、进度、引用和安全元数据，不包含模型原始推理或完整输入。

## 5. 后台任务

资料解析、智能建课、资源生成、路径规划、练习生成、报告生成和导出可能返回后台任务。典型流程：

```text
创建任务 → 保存 job_id → 查询或订阅进度 → 获取完成结果
                         ↘ 取消 / 安全重试
```

客户端应把 `job_id` 作为恢复依据，并处理 `queued`、`running`、`cancelling`、`completed`、`failed` 和 `cancelled` 等状态。

## 6. 错误处理

讲解文档首次生成调用预算 90 秒，其余结构化资源 Worker 为 45 秒，不改变课程问答超时或任务总预算。超时产物不保存为可用资源；同批成功资源保留，重新生成只补缺失类型。

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

路径规划与资源生成提交后，取消/超时不撤销产物。结果可含 `domain_committed: true` 与原产物 ID；重试先核验请求、归属和绑定，再复用产物。worker 未回写便中断时，按原 Trace 查找；冲突则阻断，不选其他版本。部分成功批次只恢复已保存资源，缺失类型仍为失败。其他工作流保留各自恢复合同。

## 10. 任务证据进度

`GET /api/v1/paths/tasks/{task_id}/progress` 只读返回指定任务版本的四个独立维度：

| 字段 | 依据 |
|---|---|
| `user_reported_completed` | 兼容旧任务完成标记，属于用户报告 |
| `activity_completed` | 已批准版本的所有 bundle 项均有验证一致的活动；测验须有已提交的绑定评估 |
| `assessment_passed` | 所有必需测验有同任务、同路径、同资源快照的完整服务端评分，得分至少 80；没有测验则为 false |
| `mastered` | 直接复用课程知识点掌握度规则，包括有效答题证据与薄弱点状态，不由任务标记推断 |

结果含活动数、事件/评估 ID、掌握分、阻断原因、`rule_version` 与 `next_step`。`study_resource`、`take_assessment`、`review_assessment` 指向精确资源；缺失、未审核或版本冲突时返回 `resolve_binding`。核验身份与版本不能证明阅读反馈的学习效果；旧计划不补造批准或评估证据。

已批准计划按上述证据推荐下一行动。工坊显示四维状态，绑定 quiz 可进入练习页。重开已提交测验复用原会话，重复交卷返回 409；读取进度、成绩和轨迹不调用模型或增加评分。完整计划编辑/批准工作台尚未提供。

## 11. 能力目录与运行历史

`GET /api/v1/agents/capabilities` 要求登录，返回已适配的输入/输出合同、Provider 协议、搜索范围与历史操作。七类 AIJob 在入队和执行前校验类型与权限，执行后校验结果，沿用超时、取消、预算、Trace 和失败分类。建课结果的课程 ID 仍为字符串；无向量时不返回 Provider/模型字段。

辅导、画像、交卷和资料对照使用领域 API/Pydantic 合同及只读 Trace，不支持通用分支或重新执行，也不另建队列。Provider 标记是协议声明（`adapter_contract_not_live_probe`），连接、结构化输出与视觉能力仍需测试及执行校验。搜索沿用 LangChain ToolNode 与严格参数合同，失败返回警告，不虚构引用或写掌握度。

| 操作 | 合同 |
|---|---|
| `POST /ai-jobs/{id}/snapshot` | 仅终态任务；首次保存后幂等返回。保存脱敏步骤、计数、产物 ID、输入摘要及校验摘要，不保存原始 Prompt、答案或密钥 |
| `GET /ai-jobs/{id}/replay` | 只读返回已保存快照；不存在为 404，校验失败为 409。不运行模型、工具、评分，也不做过期任务状态修复 |
| `POST /ai-jobs/{id}/branch` | 请求 `expected_digest` 和必填可空 `expected_active_path_id`；仅有可验证路径产物的快照支持。创建未批准草稿、任务均为 todo，保持当前计划，禁止复制学习事件和成绩；同一快照并发创建复用同一分支 |
| `POST /ai-jobs/{id}/reexecute` | 请求 `expected_digest` 和必填 `Idempotency-Key`；创建关联源快照的新 AIJob。路径强制草稿，资源仅允许原请求未绑定任务的情况；其他能力明确返回 409，请使用其领域入口 |

表中路径均以 `/api/v1` 为前缀，按用户隔离。源路径内容、资源绑定或当前基础版本变化时拒绝首次分支；摘要不匹配时拒绝重新执行。同一键复用一个新任务，不消耗旧任务重试次数；不同键创建新请求，仍受权限、并发与预算限制。`retry` 用于失败恢复，与 `reexecute` 独立。

完整运行历史工作台尚未提供。快照不能恢复模型上下文或覆盖领域数据库事实。

## 12. 模型配置与用量

### 主模型与图片验证

- `POST /settings/model/catalog` 接收 `base_url` 与可选 `api_key`，返回 `models` 模型 ID 数组。需登录；仅请求公网 HTTPS 目录，不跟随重定向。无路径的服务地址请求 `/v1/models`，已有 API 路径则追加 `/models`。兼容 `data[].id` 和 `models[].slug`，列表经排序去重；不做逐模型测试或分页补全。
- Key 留空仅复用同用户、同地址的个人密钥，不使用服务器凭证；换址需重填。目录请求不保存配置或切换默认模型，也不验证权限、额度或识图能力。获取失败或使用本地服务时手填，保存后测试连接。
- 个人主模型用于回答和生成；个人配置存在但不可用时，不自动切换到服务器凭证。
- 设置页的多配置管理复用 `/settings/model/configs` 和 `/settings/model/configs/{id}/default`。首套个人回答配置自动启用；之后新增配置仅保存，切换需用户明确确认。切换影响后续模型调用，应等待正在回答或生成的任务结束，不保证跨多个调用的任务锁定旧配置。
- 修改主模型地址需提供新 Key；免 Key 本地地址则清除旧 Key，避免向新地址发送旧凭据。地址辅助经用户确认后才移除完整接口后缀，不为自定义路径盲补 `/v1`。
- `POST /settings/model/test` 传 `{"operation":"vision"}` 会使用当前有效主模型发送合成测试图片，可能产生少量模型调用费用。验证同时检查测试图文字识别和业务结构化输出，失败不等同于模型永远不支持图片。
- 图片理解复用有效主模型的地址、模型与密钥：优先个人模型，否则使用系统模型。均须通过图片验证；未验证或失败时关闭图片输入，保留文本，不切换独立识图服务。
- 已删除独立图片默认接口、独立视觉凭证和 `SYSTEM_VISION_*` 环境配置。历史数据库字段暂留作兼容，不再读取执行，不要求破坏性数据迁移。
- 个人验证结果沿用配置记录；服务器主模型结果按用户与连接指纹保存到现有 Redis，成功有效 7 天、失败 1 小时。更换主模型/地址/Key 或状态失效后需重新验证；Redis 不可用时不开放图片输入。
- `GET /settings/model` 返回实际路由的 `can_use_vision_model` 与 `vision_status`：`not_configured`、`unverified`、`verified`、`unavailable`。
- 瞬时验证错误可重试。客户端按状态摘要判断图片可用性，不从服务器配置列表推断兜底。
- 文档上传不受图片开关影响。默认向量、排序与语音在本地处理；SearXNG 搜索仍访问互联网，无需外部搜索 Key。

语音接口要求登录：`POST /api/v1/speech/transcriptions` 接收最长 60 秒的 16 kHz 单声道 16 位 PCM，返回 `provider=sherpa_onnx`。朗读使用浏览器本地中文声音；弃用的 `POST /api/v1/speech/synthesis` 返回 410/`SPEECH_SYNTHESIS_RETIRED`，不合成音频。识别繁忙 429、空结果 422、不可用 503、超时 504 均不回退云端，见[本地语音](LOCAL_SPEECH.md)。

### 模型用量

`GET /api/v1/settings/model/usage?days=7` 要求登录，按调用时操作统计当前账号的 `chat`、`chat:*`、`stream`、`structured` 与 `vision` 用量，覆盖对话、生成、结构化及图片理解。排除向量、重排、独立搜索和未知辅助操作，但保留底层审计。筛选在数据库限额及汇总之前，次数、token、缓存率、费用与明细口径一致；切换或删除配置不隐藏历史调用。

`days` 支持 1–30 天，设置页提供 24 小时、7 天和 30 天入口。汇总最多覆盖最近 1000 条主模型调用，超出时 `truncated=true`；`recent` 展示最近 20 条。结果受调用日志保留期限限制，不代表供应商完整账单。

缺失字段为 `null`，`known_*` 仅含已知部分。缓存率按缓存读取 token / 输入 token 加权计算，任一尝试缺数据则为未知；失败与重试的已上报用量也计入。费用按调用时的显式报价估算，分币种返回已知小计和可估算调用数，未知不等于免费。读取不调用模型。

### 模型用量观测

`GET /agents/traces/{trace_id}` 按当前账号鉴权，`summary.model_calls` 返回调用类型、模型、配置 ID、会话 ID、耗时及每次尝试用量；`summary.model_usage` 汇总 token，无独立管理面板。

- `input_tokens` 是兼容接口报告的总输入，`cache_read_tokens` 是其中的缓存命中部分，不能再次相加。`reasoning_tokens` 是输出明细，不重复计入输出费用。
- `cache_write_tokens` 与 `uncached_input_tokens` 在上游未提供足够信息时为 `null`。缺失不是零；旧审计记录不会补造 token。重试包含未知消耗时，完整合计为 `null`，`known_*` 仅表示已知部分，不是总账单。
- `cache_hit_ratio` 仅在所有观察到的尝试都提供合法输入和缓存读取计数时返回。流式累计值按最后一次报告处理，不逐帧累加；取消或中断没有最终用量时保留未知。
- `observed_attempt_count` 表示实际进入适配器的尝试数；限流或取消发生在调用前可能为零。既有 `attempt_count`、`retry_count` 沿用运行时语义。SDK 内部请求行为和原生搜索工具费用不由此字段推测。
- 不保存 Key、完整提示词、回答或推理正文。观测独立提交，失败不阻断业务，不替代服务商账单。
- `estimated_cost` 默认为空。只有部署者提供明确报价且四项输入/输出计数完整时，单次调用才返回估算与报价快照。真实缓存表现需按实际服务采样，合成测试不能证明命中率。

## 13. 计划与资源

### 计划草稿与批准

- `POST /paths/generation-jobs` 传 `{"course_id":101,"draft":true}` 生成待确认草稿；从 Job 结果的 `path_id` 查询具体版本。
- `GET /paths/drafts?course_id=101` 列出最近 50 个待确认草稿；`GET /paths/{path_id}` 读取该版本及任务，含历史版本。
- `POST /paths/{path_id}/approve` 必须传 `expected_active_path_id`（首次无当前计划时显式传 `null`）。该值必须与草稿的 `plan_json.revision_of` 和当前生效计划一致，否则返回 409。重复批准同一仍生效的版本保持幂等。
- 计划返回 `approval_status`（`legacy`、`draft`、`approved`）与 `approved_at`。路径 ID 是版本身份，`schema_version` 只是结构版本，不能当批准记录。
- 草稿不改变 `/paths/current`，不能更新任务进度、生成任务资源或记录任务活动；批准后才激活。已批准计划后续重规划只生成草稿，原计划继续生效。
- 为兼容现有客户端，未指定 `draft` 且没有已批准当前计划时仍走旧生成模式，明确标记 `legacy`，不伪装为已批准。路径页手动生成使用草稿模式，支持查看任务与确认启用；陈旧草稿禁止启用，并展示生成进度与取消入口。
- 资源生成 Job 的 `result.evidence_chunk_ids` 汇总成功保存资源的真实引用（去重、最多 8 条），不是请求提供的检索上下文。中断恢复遵循同一规则；完整引用仍以各资源的 `citation_json` 为准。

批准不代表评估通过或掌握，掌握判定仍由服务端学习流程负责。资源与评估来源约束如下。

### 任务、资源与评估来源

- `GET /paths/tasks/{task_id}` 读取任务所属计划版本，包含已归档版本；草稿任务不可执行。工作台使用此接口，不把旧任务替换为当前计划任务。
- `learning_bundle.items` 返回 `binding_status` 与 `resource_version`。新绑定固定资源 ID、版本族/序号、内容和引用 SHA-256；审核 passed 且快照匹配才为 verified。旧明确关联标为 legacy_unverified，无 ID 不补造。缺失、越权、未审核或快照冲突时不返回可打开的资源 ID。
- 已绑定版本不被生成请求覆盖，缺失时返回冲突并要求新计划版本。可为尚未绑定的槽位生成资源，保存时锁定任务、复核并绑定；禁止删除带验证快照的任务来源资源。课程/账号隐私删除仍遵循既有级联规则。
- `POST /paths/tasks/{task_id}/resources/{resource_id}/practice` 从已批准计划的 verified quiz 创建练习，校验原题 ID、选项/答案与课程引用，返回既有 PracticeSessionDetail，不重生成题目。同任务/资源的并发或重复请求返回同一 session，使用 `/practice/sessions/{session_id}/answers` 评分。
- 练习响应 `source_binding` 与原题保存计划、任务、资源快照及评分合同，明确记录资源答案可见性，不作为独立盲测证明。旧练习不补造来源。
- `GET /resources/{resource_id}/learning-state?path_task_id=...` 读取该任务的活动状态；省略任务参数只读取独立资源活动。返回的 evidence 保存活动来源快照；历史空证据标记 legacy_unverified。相同 event_id 必须对应同一任务、资源和事件内容；阅读/手动完成活动不改变掌握度，也不自动完成路径任务。

## 记忆管理

接口均要求登录并按当前账号隔离，不接受调用方指定用户。记忆内容只用于不可信对话背景。

| 方法与路径 | 行为 |
| --- | --- |
| `GET /api/v1/settings/privacy` | 开关、历史经历/长期信息数量、索引数量与隐私版本 |
| `PUT /api/v1/settings/privacy` | `conversation_memory_enabled`；暂停保留记忆，恢复不自动回填 |
| `GET /api/v1/settings/privacy/memories?layer=episode&page=1&page_size=20` | `episode` / `fact` 分页，最多每页 100 条 |
| `POST /api/v1/settings/privacy/memories/facts` | `category` 为 goal/preference/difficulty/habit，`content` 最多 500 字，必须 `confirmed=true` |
| `PATCH /api/v1/settings/privacy/memories/{layer}/{id}` | `content`、`revision`、`confirmed=true`；历史摘要最多 1600 字，长期信息最多 500 字 |
| `DELETE /api/v1/settings/privacy/memories/{layer}/{id}?revision=1` | 永久删除；L2 保留无正文来源阻断标记 |
| `GET /api/v1/settings/privacy/memories/export` | 完整 JSON 导出两层记忆及来源，不含原始聊天、向量、密钥 |
| `DELETE /api/v1/settings/privacy/memory-indexes` | 仅清除派生向量，保留可查看/导出的摘要 |
| `POST /api/v1/settings/privacy/memory-indexes/rebuild` | 显式排队重建保留摘要，暂停时返回 409；不恢复已删除来源 |
| `DELETE /api/v1/settings/privacy/conversation-memory` | 清除 L2 和 L3，设置旧来源屏障；保留原始聊天 |

`MemoryItem` 返回来源会话/消息、主题、创建/更新时间、版本与索引状态。修改/删除版本过期返回 409，未找到或越权返回 404；导出、分页及管理不触发模型回答。清空不关闭记忆开关，之后新对话仍可产生新记忆。
