# EduNova API

EduNova 后端使用 FastAPI，默认 API 前缀为 `/api/v1`。当前生成合同包含 99 个路径；机器可读合同以 `backend/openapi.json` 为准。

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
