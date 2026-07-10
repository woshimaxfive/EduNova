# EduNova Agent 设计说明

更新时间：2026-07-10

## 1. 定位

EduNova 的 Agent 设计服务于学生学习闭环，不是为了展示“多智能体”概念本身。当前版本有三条 **LangGraph 生产级编排**：`HomeTutorGraph` 接管主页智能对话，`CourseTutorGraph` 接管课程问答，`ResourceGenerationGraph` 接管资源生成；其他学习闭环 Graph 暂时保持现有服务逻辑和安全 trace，后续再逐步真接管。

本轮不把认证、模型设置、Dashboard 总览等非学习能力包装成 Agent。

## 2. Graph 范围

| Graph | 生产职责 | 典型节点 |
| --- | --- | --- |
| `ProfileGraph` | 后续专项：画像抽取、画像审核、画像事件持久化 | profile_extract、profile_review、persist |
| `CourseBuilderGraph` | 后续专项：资料读取、课程结构、知识点、切片、embedding、审核、持久化 | material_read、structure、knowledge_points、chunks、embedding、review、persist |
| `MaterialComparisonGraph` | 后续专项：资料证据收集、重点/考点/遗漏点提炼、引用审核 | evidence、compare、exam_points、gap_analysis、review |
| `HomeTutorGraph` | 已真接管：安全上下文、问题路由、选中资料检索、按需联网、深度规划、回答、审核/修订和消息持久化 | context、route、material_retriever、web_search、planner、answer、review、repair、persist |
| `CourseTutorGraph` | 已真接管：画像/上下文读取、课程检索、导师回答、弱点候选、审核、下一步动作、消息持久化 | profile、retriever、tutor、weakness、review、next_action |
| `ResourceGenerationGraph` | 已真接管：画像、检索、诊断、规划、六 Worker 并行生成、聚合、模型与规则审核、单次修订、持久化 | profile、retrieve、diagnosis、planner、resource_worker、aggregate、review、repair、persist |
| `PathPlanningGraph` | 后续专项：画像/弱点/资源证据收集、路径排序、任务生成、审核、持久化 | profile、evidence、rank、tasks、review、persist |
| `ExamSprintGraph` | 后续专项：冲刺证据收集、高频点/必刷题/易错提醒生成、审核、持久化 | evidence、high_frequency、must_practice、mistakes、review、persist |
| `AssessmentGraph` | 后续专项：出题、作答评估、弱点同步、审核、持久化 | question_plan、evaluate、weakness_sync、review、persist |
| `ReportGraph` | 后续专项：练习/掌握度/弱点聚合、报告生成、审核、持久化 | aggregate、report、review、persist |
| `ExportDossierGraph` | 后续专项：学习档案聚合、Markdown 渲染、隐私审核、返回下载内容 | aggregate、render_markdown、privacy_review、return |

`Service` 仍然是 API 边界和依赖装配层。主页问答、课程问答和资源生成的核心流程已经委托给对应 Graph runner；其他学习流程暂时通过服务逻辑产出兼容 trace，不把它们写成已经真接管。

## 3. AgentState

共享状态字段在 `backend/app/agents/schemas.py` 中定义，核心字段包括：

```text
trace_id
workflow
user_id
course_id
knowledge_point_id
artifact_type
artifact_id
profile_summary
retrieved_chunks
citations
diagnosis
generated_resources
review_result
warnings
errors
node_results
artifact_refs
selected_material_ids
conversation_context
retrieval_query
plan_summary
repair_count
```

`review_result` 必须包含 `review_status`、`confidence`、`risk_flags` 和 `safety_summary`。前端展示的是课堂协作轨迹，不展示原始思维链、系统提示词、完整模型输入、API Key、完整资料原文或完整用户画像原文。

## 4. Trace 存储

`agent_run_logs` 保存节点轨迹，`/api/v1/agents/traces/{trace_id}` 按当前用户隔离查询，并返回：

- `trace_id`、`workflow`、`artifact_type`、`artifact_id`、`course_id`。
- `status`：由步骤状态派生，可能为 `running`、`completed`、`warning` 或 `failed`。
- `steps`：按 `step_index`、`created_at`、`id` 排序。
- `metadata`：只包含白名单安全摘要。

以下学习产物新增 nullable `agent_trace_id` 并建立索引，便于从前端产物反查 Graph：

- `courses.agent_trace_id`
- `materials.agent_trace_id`
- `course_materials.agent_trace_id`
- `generated_resources.agent_trace_id`
- `learning_paths.agent_trace_id`
- `practice_sessions.agent_trace_id`
- `assessment_reports.agent_trace_id`

`chat_messages.trace_id` 保持既有字段。`export_jobs.agent_trace_id` 同时服务异步学习档案和资源 PPTX；`resource_id` 把 PPTX 任务关联到对应的 `generated_resources`。

## 5. Metadata 白名单

允许记录：

- `trace_id`、`workflow`、`artifact_type`、`artifact_id`、`course_id`、`knowledge_point_id`。
- Agent 名称、步骤序号、状态、耗时。
- 输入摘要和输出摘要。
- 引用的知识点、章节、来源标题、页码和短摘录。
- 质量分、审核状态、生成模式、错误类型、风险标记和 warning 数量。
- 会话上下文只记录安全计数和模式：`context_message_count`、`context_summary_used`、`retrieval_query_mode`，不记录历史消息原文。

禁止记录：

- 完整系统提示词。
- 完整模型输入。
- API Key、JWT、密码和连接密钥。
- 完整用户画像原文。
- 完整上传资料原文。
- 完整用户作答原文。

## 6. 失败恢复

EduNova 的第一版坚持确定性可用稿优先：

- 模型未配置时，课程资源、路径、练习、报告和导出仍应尽量基于课程引用和规则产出可解释结果。
- 模型调用失败时，不把模板占位伪装成模型结果，Graph trace 会记录 warning 或风险标记。
- 资料依据不足时，用 `low_evidence` 或明确空状态表达，不编造引用。
- 课程问答没有依据时提示资料不足，不伪造课程引用。
- 主页允许使用模型通用知识，但资料和网页引用必须来自真实检索。`material_retriever` 只搜索当前用户本次选中的资料，无相关片段时返回空资料来源，不把资料开头冒充答案依据。
- 主页回答要求 `<final_answer>` 输出边界；规则和模型 ReviewAgent 共同识别 Prompt 回显、跑题、Markdown 结构、引用错配、假网页来源和敏感输出。审核不通过最多执行一次 `repair`，第二次仍失败使用清晰降级回答。
- 模型 Review JSON 无效或 Provider 暂不可用时，Review 节点记录 `warning`，不得伪装为 `passed`。
- 生成型 Graph 必须经过 ReviewAgent 节点，输出审核状态、置信度、风险标记和安全摘要。
- 资源 Graph 的每个类型由独立 Worker 调用模型；Worker 失败时只降级该类型，其他分支继续。ReviewAgent 批量复核六类产物，失败内容最多进入一次 RepairAgent，仍不安全则不持久化。

## 7. 前端呈现

- 课程空间把回答下方“思考过程”改为“课堂协作轨迹”，展示 Profile、Retriever、Tutor、Weakness、Review、NextAction。
- 课程空间顶部用 A3 个性化学习闭环摘要和固定步骤流解释画像、检索、辅导、弱点、资源、路径、评估、报告的协作关系；这是面向用户的过程证据，不是原始思维链。
- 课程回答展示层和生成层都必须过滤 `学生问题`、`课程引用`、`匹配度`、资料片段等模型输入字段；引用证据只进入来源面板，不作为回答正文泄露。
- 主页会话和课程空间会话默认使用同一 `session_id` 内最近 12 条消息作为多轮上下文；更早历史只生成确定性安全摘要。课程 RAG、主页资料上下文和联网搜索会用最近用户问题 + 当前问题做上下文化查询，前端只展示“已参考最近 N 条会话”等安全提示。
- 资源工坊和课程空间共用结构化资源渲染器，展示 Markmap、交互练习、浏览器 Python、PPT、动画图解和 `ResourceGenerationGraph` 全链路；旧 Markdown/Mermaid 资源继续降级可读。
- 学习路径、练习和报告页面显示轻量 trace 入口；这些页面后续再升级为真实 Graph 编排。
- 主页发送后通过 SSE 展示安全 Graph 状态、真实来源、Markdown token 和可选 Review 替换；`done` 后用持久化消息校准。深度思考只展示规划和处理摘要，不展示原始思维链。
- 所有 trace 读取失败都只影响局部轨迹区，不阻断学习主流程。

## 8. 答辩解释口径

可以这样解释 EduNova 的多智能体：

```text
EduNova 不是把所有逻辑都交给大模型，而是把学生学习链路拆成画像、检索、资源、路径、评估、报告等可审计 Graph。
每个 Graph 都有明确的数据边界、证据来源、ReviewAgent 审核和安全 trace。
模型负责增强表达，规则和课程引用负责保证结果可复现、可解释、可在无模型环境下演示。
```

## 9. 后续打磨

- 增强资料对比结果和期末冲刺、路径排序之间的证据联动。
- 补浏览器 E2E，把 Graph trace 可见性纳入主链路验收。
- 在不泄露原始输入的前提下继续丰富 AgentTimeline 的白名单 metadata。
