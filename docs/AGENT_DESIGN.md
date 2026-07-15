# EduNova Agent 设计说明

更新时间：2026-07-15

## 1. 定位

EduNova 的 Agent 设计服务于学生学习闭环，不是为了展示“多智能体”概念本身。当前版本有十条 **LangGraph 生产级编排**：`MaterialIngestionGraph`、`ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph` 和 `MaterialComparisonGraph`。

本轮不把认证、模型设置、Dashboard 总览等非学习能力包装成 Agent。

## 2. Graph 范围

| Graph | 生产职责 | 典型节点 |
| --- | --- | --- |
| `ProfileGraph` | 已真接管：显式画像回答和学习行为信号的抽取、证据门控、审核/修订、应用与事件持久化；Lite 输出经过白名单 Schema、容错 JSON 解析和单次结构修复 | collect_context、extract、evidence_gate、review、repair、apply、persist_event |
| `CourseBuilderGraph` | 已真接管：资料读取、来源大纲、课程结构、知识点、切片、embedding、审核/修订和事务持久化 | read_materials、source_outline、structure_course、knowledge_points、chunk、embed、review、repair、persist |
| `MaterialComparisonGraph` | 已真接管：范围校验、真实分块证据收集、概念别名归并、规则对比、模型解释增强、审核/修订和不可变版本持久化 | validate_scope、collect_evidence、deterministic_compare、model_compare、review、repair、persist |
| `HomeTutorGraph` | 已真接管：安全上下文、自动能力路由、选中资料检索、按需联网、自适应规划、回答、审核/修订和消息持久化 | context、route、material_retriever、web_search、planner、answer、review、repair、persist |
| `CourseTutorGraph` | 已真接管：画像/上下文读取、自动能力路由、课程检索、外部补充、规划、导师回答、弱点候选、审核、下一步动作和消息持久化 | profile、route、retriever、web_search、planner、tutor、weakness、review、next_action |
| `ResourceGenerationGraph` | 已真接管：画像、检索、诊断、逐类型教学意图规划、六 Worker 并行生成 v3 artifact、真实性/个性化/差异审核、结构/内容修订、代码运行验证和版本化持久化 | profile、retrieve、diagnosis、planner、resource_worker、aggregate、review、repair、persist |
| `PathPlanningGraph` | 已真接管：画像与证据收集、确定性排序、模型排序理由、审核/修订、事务持久化 | profile、collect_evidence、deterministic_rank、model_plan、review、repair、persist |
| `AssessmentGraph` | 已真接管：资料证据型题目蓝图、模型增强、确定性题目门禁和评分、逐题错因诊断、弱点同步和路径回流 | context/question_plan/generate_questions/review/repair/persist；load/deterministic_score/diagnose_errors/sync_weaknesses/review/repair/persist/path_replan |
| `ReportGraph` | 已真接管：最近练习、掌握度、弱点、路径和资源聚合，不可变统计、叙事增强、审核/修订和持久化 | collect_practice、collect_mastery、aggregate_evidence、generate_narrative、review、repair、persist |
`Service` 仍然是 API 边界和依赖装配层。十条主链路的核心流程已经委托给对应 Graph runner。学习档案导出是确定性 Service + Redis/RQ Worker，不注册为 `ExportDossierGraph`，也不把异步任务包装成 Agent。

Phase 17 新增的 `AIJobRuntime` 也不是第十一条 Agent Graph。它只为 `CourseBuilderGraph` 和 `ResourceGenerationGraph` 提供后台排队、节点进度、心跳、取消、重试和刷新恢复。任务和 Graph 共用同一个 `agent_trace_id`；Graph trace 仍由真实节点执行产生，任务进度不替代 `agent_run_logs`。

Phase 18 新增的 `ModelExecutionRuntime` 同样不是 Agent Graph。它位于模型配置与 Provider 之间，为生产 Graph、主页/课程流式问答和 Embedding 提供统一错误分类、同配置重试、Redis 并发/熔断、取消检查和 `model_call_runs` 安全审计。模型失败后仍由各 Graph 的规则底稿接管，`rules_only` 不伪装成模型审核。

`ProfileGraph.extract` 会向模型提供当前八维画像的安全摘要、逐维可信度和本次回答，要求输出 `updates/confidence/uncertain_dimensions`。纯 JSON、代码块 JSON 和正文内首个完整 JSON 均可解析；首次无效只调用一次格式修复。有效模型字段不依赖人工关键词准入，同一维度由模型语义结果优先，规则只补充模型遗漏的高确定性字段；关键词提示仅用于识别可能遗漏的维度并选择下一问。有效模型提案必须进入 ReviewAgent，不确定陈述只形成候选证据；模型不可用、结构连续无效或审核拒绝后使用增强中文规则并记录 `rules_only`、解析状态和修复次数。

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
search_required
reasoning_mode
tool_reason_codes
repair_count
```

`review_result` 必须包含 `review_status`、`confidence`、`risk_flags` 和 `safety_summary`。前端展示的是课堂协作轨迹，不展示原始思维链、系统提示词、完整模型输入、API Key、完整资料原文或完整用户画像原文。

## 4. Trace 存储

`agent_run_logs` 保存节点轨迹，`/api/v1/agents/traces/{trace_id}` 按当前用户隔离查询，并返回：

- `trace_id`、`workflow`、`artifact_type`、`artifact_id`、`course_id`。
- `status`：由步骤状态派生，可能为 `running`、`completed`、`warning` 或 `failed`。
- `steps`：按 `step_index`、`created_at`、`id` 排序。
- `metadata`：只包含白名单安全摘要。
- 最后一个步骤可聚合当前 trace 的模型调用次数、重试次数、总耗时、降级结果和安全错误分类。

以下学习产物新增 nullable `agent_trace_id` 并建立索引，便于从前端产物反查 Graph：

- `courses.agent_trace_id`
- `materials.agent_trace_id`
- `course_materials.agent_trace_id`
- `generated_resources.agent_trace_id`
- `learning_paths.agent_trace_id`
- `practice_sessions.agent_trace_id`
- `assessment_reports.agent_trace_id`

`chat_messages.trace_id` 保持既有字段。`export_jobs.agent_trace_id` 同时服务异步学习档案和资源 PPTX；`resource_id` 把 PPTX 任务关联到对应的 `generated_resources`。

`ai_jobs.agent_trace_id` 绑定后台任务与对应 Graph trace。`request_json` 只允许资料/课程/知识点 ID、资源类型、目标和难度；`result_json` 只允许课程/资源 ID、warning 和失败资源类型。任务步骤只记录节点名、状态、百分比、资源类型和更新时间。

## 5. Metadata 白名单

允许记录：

- `trace_id`、`workflow`、`artifact_type`、`artifact_id`、`course_id`、`knowledge_point_id`。
- Agent 名称、步骤序号、状态、耗时。
- 输入摘要和输出摘要。
- 引用的知识点、章节、来源标题、页码和短摘录。
- 质量分、审核状态、生成模式、错误类型、风险标记和 warning 数量。
- 资源教学意图数量、生成动作、历史摘要数量、差异风险、版本号和版本族安全标识；不记录完整画像或历史成果正文。
- 会话上下文只记录安全计数和模式：`context_message_count`、`context_summary_used`、`retrieval_query_mode`，不记录历史消息原文。
- 自动能力只记录 `search_required`、`reasoning_mode`、预定义原因码和课程/网页来源数量，不记录用户问题原文或模型思维链。

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
- 资源 Graph 的 planner 先为每类资源制定 `ArtifactIntent`，六个独立 Worker 再按互补职责输出类型化 artifact。ReviewAgent 读取意图、证据短摘录、完整候选内容和历史摘要，检查真实性、个性化与差异。讲解、导图、PPT 只有通过证据门禁才允许规则降级；练习、代码和动画未通过门禁直接失败。代码必须经过内部 Pyodide 验证，服务不可用时不得保存。
- `AssessmentGraph` 的客观答案和分数不可被模型覆盖；模型只增强题面、干扰项、解析和逐题错因。题目 ReviewAgent 读取完整题目与安全证据，错因 ReviewAgent 读取题干、正确答案、学生答案、分数和诊断；规则修订不伪装成模型审核通过。
- `PathPlanningGraph` 不自动创建用户从未建立的路径；用户主动建立路径后，系统根据画像目标、弱点、掌握度和课程结构给出有序任务。路径不生成日期或期限；练习重排保留已完成任务和未受影响的当前任务，审核成功后才归档旧 active 路径。
- `ReportGraph` 分别锁定练习会话数、已作答题数、正确题数、已评估知识点数、已完成任务数和趋势；模型只生成总结和建议。叙事出现额外数字或统计混淆时触发一次修订，修订稿再次经过完整审核。

## 7. 前端呈现

- 课程空间“课堂协作轨迹”展示 Profile、Route、Retriever、WebSearch、Planner、Tutor、Weakness、Review、NextAction；跳过节点仍说明安全决策，不展示原始思维链。
- 课程空间顶部用 A3 个性化学习闭环摘要和固定步骤流解释画像、检索、辅导、弱点、资源、路径、评估、报告的协作关系；这是面向用户的过程证据，不是原始思维链。
- 课程回答展示层和生成层都必须过滤 `学生问题`、`课程引用`、`匹配度`、资料片段等模型输入字段；引用证据只进入来源面板，不作为回答正文泄露。
- 主页会话和课程空间会话默认使用同一 `session_id` 内最近 12 条消息作为多轮上下文；更早历史只生成确定性安全摘要。课程 RAG、主页资料上下文和联网搜索会用最近用户问题 + 当前问题做上下文化查询，前端只展示“已参考最近 N 条会话”等安全提示。
- 资源工坊和课程空间共用结构化资源渲染器，展示 Markmap、交互练习、浏览器 Python、PPT、动画图解和 `ResourceGenerationGraph` 全链路；资源工坊额外按版本族提供切换、比较、换教法和优化版本，并展示安全的“为什么为你这样生成”。旧 Markdown/Mermaid 资源继续降级可读。
- 学习路径、练习和报告页面通过共享 `AgentTraceDisclosure` 展开真实 PathPlanning、Assessment、Report 节点轨迹；局部轨迹失败不阻断主流程。
- 主页和课程空间不显示联网/思考开关。发送后通过 SSE 展示实际发生的安全 Graph 状态、真实来源、Markdown token 和可选 Review 替换；规划只展示安全摘要，不展示原始思维链。
- 所有 trace 读取失败都只影响局部轨迹区，不阻断学习主流程。

## 8. 答辩解释口径

可以这样解释 EduNova 的多智能体：

```text
EduNova 不是把所有逻辑都交给大模型，而是把学生学习链路拆成画像、检索、资源、路径、评估、报告等可审计 Graph。
每个 Graph 都有明确的数据边界、证据来源、ReviewAgent 审核和安全 trace。
模型负责增强表达，规则和课程引用负责保证结果可复现、可解释、可在无模型环境下演示。
```

## 9. 后续打磨

- 继续验证资料对比、持续学习路径和针对性练习的跨页面恢复与失败分支。
- 扩展隔离 Docker E2E，把十条 Graph 的跨页面回流持续纳入验收。
- 在不泄露原始输入的前提下继续丰富 AgentTimeline 的白名单 metadata。

## 10. 可信画像上下文

- 系统只保存一份用户级长期画像。`CourseLearnerContext` 是请求时派生的安全视图，组合可信总画像维度与当前课程掌握度、弱点、路径、练习、资源和报告。
- 画像维度按证据可信度分层：至少 70% 可直接个性化，50-69% 仅作弱提示，低于 50% 或候选状态不进入下游上下文。
- ProfileGraph 的逐维分数由抽取置信度、来源系数、审核系数和独立来源奖励组成；候选不计入画像轮廓，明确修改后仅使用支持当前值的证据重算，因此分数可以下降。
- 除资料解析外的九条学习 Graph 统一记录 `profile_applied_version`、可信维度数、完整度和课程上下文版本。资料解析不读取学生画像。trace 只披露计数和版本，不披露画像原文。
- 新资源、路径和报告保存画像应用版本与课程上下文 hash；画像变化只产生 `stale` 提示，不自动重跑 Graph。

## 11. MaterialIngestionGraph 与 CourseBuilderGraph

`MaterialIngestionGraph` 是用户资料进入 RAG 和建课前的独立质量门，节点固定为：

```text
validate -> extract_pages -> normalize_layout -> detect_outline
-> model_refine -> chunk -> quality_gate -> persist
```

规则负责页码、标题、章节边界、重复页眉页脚、异常字符和质量阈值；模型只修正歧义标题与层级，不接收整本教材。解析成功后只进入待确认状态，用户确认目录版本后才能作为生产证据。

`CourseBuilderGraph` 节点固定为：

```text
validate_confirmed_materials -> coherence_gate -> load_outlines
-> chapter_plan -> concept_workers -> aggregate -> prerequisite_graph
-> evidence_bind -> review -> repair -> persist
```

`concept_workers` 通过 LangGraph `Send` 按章节并行，每个 Worker 只读取本章节切片。模型负责语义归纳与教学结构，规则负责来源覆盖、知识点密度、标题质量、引用存在性、先修 DAG 和事务门禁。任何知识点没有真实切片证据时，整门课程不得持久化。
