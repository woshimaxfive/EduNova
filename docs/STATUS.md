# EduNova 当前状态

更新时间：2026-07-05

## 状态摘要

当前最新完成到 **Phase 10：练习评估与学习报告闭环第一刀**。

Phase 计划继续以 `docs/superpowers` 原始实施计划为准。Phase 7 已按“对话式学习画像”主线收口；Phase 7.3 和 Phase 7.4 前置补齐课程级弱点队列基础，是为了让画像证据能落到课程状态里，不改变后续 Phase 编号。Phase 8 已完成 Agent 可观测底座、5 类课程资源生成和资源质量收口；Phase 9 已完成课程级学习路径、规则掌握度图、弱点队列推荐资源和复习时间第一版；Phase 10 已完成真实练习生成、确定性批改、弱点/掌握度反哺和学习报告展示第一刀。

这一阶段之后，EduNova 已经从前端骨架推进到真实学生学习底座：

- 账号、首页、资料库、规则建课、课程知识库和课程会话都已经接入真实后端。
- 课程空间可以基于当前用户课程资料检索引用。
- 命中引用后可以调用当前用户默认模型配置生成回答。
- 课程回答支持 SSE 流式输出，完成后持久化消息、引用和 `trace_id`。
- RAG 检索已经从纯关键词升级到关键词 + 1536 维向量混合召回。
- 主页会话已经从固定模板回复改为调用当前用户默认模型生成通用回答。
- 课程空间已经从常驻面板页改为默认问答模式 + 按需学习模式。
- 学习画像已从前端骨架推进为真实后端画像、画像事件和课程问答画像候选事件。
- Phase 7.2 已明确用户级画像和课程级学习状态的边界：用户级画像只有一份，课程级目标、薄弱点、掌握度、复习队列和学习路径按课程聚合。
- Phase 7.3 已把课程问答弱点候选事件同步为课程级 `weakness_review_queue` 待确认复习项，并在课程空间展示真实“待复习弱点”摘要。
- Phase 7.4 已为课程级弱点复习项补齐确认、开始、完成和软忽略状态流转，课程空间可以直接操作真实队列项。
- Phase 8.1 已挂载 `/agents/traces/{trace_id}`，复用 `agent_run_logs` 查询当前用户自己的 Agent 轨迹，并在课程空间“思考过程”面板读取真实 trace；同时新增 LangGraph `profile -> retrieve -> diagnosis -> resource -> review -> persist` 骨架。
- Phase 8.2 已挂载 `/resources`，可基于当前用户课程生成讲解、思维导图、练习、代码实操和 PPT 大纲，并写入资源、质量分和 Agent 轨迹；Phase 8.2.1 已改为课程引用驱动的确定性可用稿优先，模型只做批量增强，模型不可用或失败时不再把可用资源降级为空模板。
- Phase 9 已挂载 `/paths`，可为当前用户课程生成 active 学习路径、更新任务状态，并把 `/app/path` 接入真实课程、任务、路径依据和掌握度图。
- Phase 9 已实现 `/courses/{course_id}/mastery-map`，并让 `/courses/{course_id}/learning-state` 返回真实路径摘要、掌握度摘要、弱点推荐资源和下次复习时间。
- Phase 10 已挂载 `/practice` 和 `/reports`，可创建课程练习、提交作答、确定性批改、把错题或低分题写入 `practice_assessment` 来源的 `confirmed` 弱点，并生成/读取课程学习报告。

Phase 8 暂按“可用完成”收口：Agent trace 底座、5 类课程资源生成、质量门槛和模型无关可用稿已经能支撑产品主链路和演示验收。保留的 Phase 8 hardening backlog 只包括资源工坊直接展示资源生成 trace、AgentTimeline 补充白名单 metadata、后续评估让 LangGraph 真正接管生成编排；这些不再拆成新的 Phase 8.x，也不阻塞 Phase 11。

当前仍然不是完整产品。课程级路径、掌握度图、弱点队列、练习评估和学习报告第一刀已经接入，但错题驱动的深度薄弱点追溯、报告文件导出、期末冲刺、资料对比、演示模式重置和深度文档解析还在后续阶段。

## 已完成主链路

| 范围 | 当前能力 | 关键入口 |
| --- | --- | --- |
| 认证 | 注册、登录、读取当前用户、退出、受保护路由 | `/api/v1/auth/*` |
| 首页总览 | 当前用户课程、资料、主页历史和空状态 | `/api/v1/dashboard/summary` |
| 主页会话 | 主页首次发送、连续追问、通用模型回答、历史切换和刷新保留 | `/api/v1/tutor/sessions` |
| 资料库 | 上传、列表、详情、解析进度、课程关联 | `/api/v1/materials/*` |
| 规则建课 | 已解析 TXT/Markdown 资料生成课程、知识点和切片 | `/api/v1/courses/from-materials` |
| 课程详情 | 课程列表、详情、概览、知识点 | `/api/v1/courses/*` |
| RAG 检索 | 当前用户课程内关键词/向量混合检索 | `/api/v1/rag/search` |
| 课程会话 | 课程内历史、消息、引用持久化和刷新恢复 | `/api/v1/tutor/sessions?scope=course` |
| 模型设置 | 多套个人模型配置、默认配置、连接测试、服务器兜底 | `/api/v1/settings/model/configs` |
| 课程回答 | 非流式与流式课程 RAG 回答 | `/messages`、`/messages/stream` |
| Embedding | OpenAI-compatible `/embeddings` 与本地 fallback | `EmbeddingService` |
| 学习画像 | 8 维用户级画像、画像对话更新、画像事件、课程问答候选事件和课程状态分层边界 | `/api/v1/profiles/*` |
| 课程学习状态 | 当前课程画像叠层、弱点候选计数、复习队列和状态流转 | `/api/v1/courses/{course_id}/learning-state` |
| Agent 轨迹 | 当前用户自己的 Agent trace 查询、步骤排序和安全摘要返回 | `/api/v1/agents/traces/{trace_id}` |
| 课程资源 | 生成 5 类课程学习资源、质量分和资源生成 Agent trace | `/api/v1/resources/*` |
| 学习路径 | 生成课程级 active 路径、更新路径任务、读取当前路径 | `/api/v1/paths/*` |
| 掌握度图 | 按课程知识点、弱点队列、路径任务、资源推荐和练习结果计算规则掌握度 | `/api/v1/courses/{course_id}/mastery-map` |
| 练习评估 | 创建课程练习、提交作答、确定性批改并反哺弱点队列 | `/api/v1/practice/*` |
| 学习报告 | 基于课程、练习、掌握度和弱点生成真实报告 | `/api/v1/reports/*` |

## 当前前端状态

| 页面 | 当前状态 |
| --- | --- |
| `/login` | 调用真实登录接口，不提供共享演示学生按钮 |
| `/register` | 调用真实注册接口，可选择空白开始或复制人工智能导论 |
| `/app` | GPT 式主页，真实读取 summary、主页历史、最近课程和资料库浮层；发送后调用主页通用模型回答 |
| `/app/library` | 文件库式资料库，真实读取资料列表，支持上传、搜索、筛选和详情 |
| `/app/courses/:courseId` | 默认问答模式 + 按需学习模式；读取真实课程、知识点、课程历史、消息、引用、课程学习状态和 Agent trace，支持流式课程问答，可确认/开始/完成/忽略待复习弱点，知识点入口和引用可进入学习模式 |
| `/app/settings` | 管理多套模型配置，支持 Provider 预设、保存、测试、设默认和删除 |
| `/app/studio` | 真实资源工坊，读取课程、知识点和当前用户资源，可生成 5 类课程资源并展示模型增强/本地可用稿/低依据、引用和质量分 |
| `/app/profile` | 读取真实 8 维画像、画像事件和画像对话更新；空画像显示待补充，不展示静态假画像 |
| `/app/tutor` | 课程辅导入口，读取当前用户课程并跳转对应课程空间，不再展示静态假问答 |
| `/app/practice` | 读取真实课程和知识点，创建课程练习、作答、提交并展示即时反馈和复习线索 |
| `/app/reports` | 读取真实课程和最新报告，可生成学习报告；展示真实分数、掌握度更新、薄弱点、证据摘要和下一步建议，不做假导出 |

当前前端不再使用中间横向的 `ActionNotice` 提示。历史切换、筛选、开关和详情展开依靠选中态或内容变化表达；上传失败、发送失败、课程生成失败和表单校验错误使用局部提示；模型配置保存、测试、设默认和删除使用右下角轻量 toast。

主页输入区的资料状态只显示已选资料数量，并贴近底部输入框；联网搜索和深度思考目前仍是预备能力，只通过按钮高亮和 `aria-pressed` 表达，不显示“已联网搜索”之类的能力暗示。

课程空间 Phase 6.5 已落地“默认问答模式 + 按需学习模式”。默认问答模式保持课程版 ChatGPT 体验，真实引用、生成资源、学习路径和思考过程在回答下方渐进展开；知识点不再以横向列表常驻首屏，而是通过轻量入口进入学习模式后选择，引用来源可直接进入学习模式。学习模式中间显示学习内容，右侧提供上下文 AI 辅导。Phase 8.1 后，“思考过程”会在存在 `latest_trace_id` 时读取真实 Agent trace；Phase 8.2 后，“生成资源”入口会跳转到资源工坊并带上当前课程；Phase 9 后，“学习路径”读取真实 `path_summary` 并跳转 `/app/path?course_id=...`；Phase 10 后，课程行动入口会带 `course_id` 跳转 `/app/practice` 和 `/app/reports`。

## 当前后端状态

| 模块 | 当前状态 |
| --- | --- |
| FastAPI 应用 | 已有 `/api/health` 和 `/api/v1` 路由结构 |
| 数据库 | PostgreSQL + pgvector，Alembic 迁移到当前 head |
| 课程包 | 人工智能导论内置课程包可幂等导入 |
| 认证 | bcrypt、JWT、`starter_mode` 和当前用户依赖已接入 |
| 资料库 | 独立 `materials` 和 `course_material_links` 已接入 |
| 课程 | TXT/Markdown 规则建课、课程学习状态、待确认弱点队列同步和状态流转已接入 |
| RAG | 混合检索、引用字段和检索状态已接入 |
| 模型 | OpenAI-compatible chat、stream、embeddings 已接入 |
| 学习画像 | `profiles` router 已接入，复用 `student_profiles` 和 `profile_events`；不为每门课复制完整画像 |
| Agent 轨迹 | `agents` router 已接入，复用 `agent_run_logs`，支持当前用户 trace 查询和安全摘要返回 |
| 课程资源 | `resources` router 已接入，复用 `generated_resources`、`resource_quality_scores` 和 `agent_run_logs`，支持 5 类课程资源同步生成 |
| 学习路径 | `paths` router 已接入，复用 `learning_paths` 和 `learning_tasks`，支持课程级路径生成和任务状态更新 |
| 练习评估 | `practice` router 已接入，复用 `practice_sessions`、`practice_answers` 和 `weakness_review_queue`，支持确定性出题、批改和弱点反哺 |
| 学习报告 | `reports` router 已接入，复用 `assessment_reports`，支持课程最新报告读取和报告生成 |
| Docker | Compose 五服务可按默认端口启动；后端容器已支持 Alembic 配置读取；前端镜像构建不复用本机 `node_modules` |
| 安全 | 用户数据隔离、Key 加密、脱敏返回和上传目录忽略已接入 |

当前后端已挂载的业务 router 是 `auth`、`dashboard`、`courses`、`materials`、`profiles`、`rag`、`settings`、`tutor`、`agents`、`resources`、`paths`、`practice` 和 `reports`。`demo` 仍只是前端 API 常量与后续接口设计，不属于当前已实现后端能力。

资源分层口径：`generated_resources.course_id != null` 是课程资源，Phase 8.2 只生成这一类；`course_id == null` 预留为后续个人全局资源，本阶段不提供生成入口。资源生成在 Phase 8.2.1 后固定为“确定性可用稿优先，模型批量增强”：本地 draft 先保证 5 类资源具备可读、可练、可复用结构，模型未配置、调用失败、解析失败、输出缺失或输出含敏感标记时保留对应资源的本地可用稿。`content_json.metadata.generation_mode` 区分 `model_enhanced`、`deterministic_source` 和 `low_evidence_fallback`；`review_status="passed"` 表示资源通过本地质量门槛，不要求一定来自模型，`low_evidence` 只表示课程依据不足。资源、质量分和 Agent trace 均不保存系统提示词、完整模型输入、API Key、完整课程资料原文或完整用户画像原文。

课程问答在 Phase 7.1 后会把明确困惑/薄弱信号沉淀为画像候选事件，但只保存课程、会话、消息、`trace_id` 和引用摘要，不保存完整用户问题、系统提示词、模型输入或资料原文。Phase 7.3 的 `/courses/{course_id}/learning-state` 会把当前课程的这些候选事件按知识点或安全标题同步为 `pending` 待确认复习项，不把候选事件直接宣称为已诊断弱点。Phase 7.4 后，学生可以把队列项确认为 `confirmed`、开始为 `reviewing`、完成为 `completed`，也可以软忽略为 `dismissed`；`dismissed` 不在主列表展示，但继续参与去重。

Phase 7.2 的分层口径：

- `student_profiles` 保存用户级长期画像，只保留一份。
- `profile_events` 保存证据流，可带课程来源信息。
- `weakness_review_queue` 保存课程级可执行复习项，Phase 7.3 已接入课程问答候选事件到 `pending` 项的同步，Phase 7.4 已接入确认、开始、完成和软忽略状态流转，必须绑定 `course_id`。
- `learning_paths` 和 `learning_tasks` 保存 Phase 9 生成的课程级 active 路径和任务，旧 active 路径会归档为 `archived`。
- `/courses/{course_id}/learning-state` 是课程级学习状态聚合接口，不新增通用 `learning_events` 表；Phase 9 后同时返回路径摘要、掌握度摘要、推荐资源和复习时间，Phase 10 后练习结果会反哺掌握度和 `practice_assessment` 来源弱点。

课程空间和普通二级路由已经去掉前端 demo 数据兜底：真实课程加载中不会显示“人工智能导论”示例课程，资源工坊初始不展示假生成队列，报告页不展示固定资料证据，普通二级路由侧栏不再注入主页 demo 历史。

## 尚未完成

| 能力 | 当前处理 |
| --- | --- |
| PDF/PPTX/DOCX 深度解析 | 资料可以入库，但不能用于规则建课 |
| OCR 和图片题目识别 | 图片只入库，不做识别 |
| 讯飞原生 Embeddingp/Embeddingq | 暂不接入，当前用 OpenAI-compatible embeddings 或本地 fallback |
| 期末冲刺与资料对比 | 仍未进入 Phase 11 |
| 资源增强 | Phase 8.2.1 已支持 5 类课程资源的模型无关可用稿、可选模型增强和规则质量分；资源编辑、异步任务队列、个人全局资源生成入口和推荐资源消费未接入 |
| Agent 编排 hardening | Phase 8 已可用收口；资源工坊 trace 展示、AgentTimeline metadata 和 LangGraph 真正接管生成编排作为后续 hardening backlog，不阻塞 Phase 11 |
| 弱点复习增强 | Phase 10 已接入练习评估来源；错题驱动的更细粒度追溯、队列项编辑和练习再推荐未接入 |
| 学习路径 | Phase 9 已接入真实路径生成、当前路径读取、任务状态更新和课程页摘要 |
| 掌握度图 | Phase 10 已接入练习评估修正；仍是规则计算，不单独持久化 |
| 学习报告导出 | Phase 10 已接入真实报告生成和页面展示；文件导出未接入 |
| 演示模式重置 | 入口保留，真实重置流程未接入 |

## 阶段对照

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Phase 0-2 | 已完成 | 基础文档、工程骨架、数据库迁移、核心表和内置课程包 |
| Phase 3 | 已完成 | 学生端前端骨架、主页体验、资料库、课程空间和核心页面 |
| Phase 4.1 | 已完成 | 真实认证闭环 |
| Phase 4.2 | 已完成 | 首页真实总览 |
| Phase 4.3 | 已完成 | 主页会话与消息持久化 |
| Phase 4.4 | 已完成 | 真实资料库上传与列表 |
| Phase 5.1 | 已完成 | TXT/Markdown 规则建课 |
| Phase 5.2 | 已完成 | 课程知识库检索与引用 |
| Phase 5.3 | 已完成 | 课程空间会话与引用持久化 |
| Phase 6.1 | 已完成 | 模型 Provider 与非流式课程 RAG 回答 |
| Phase 6.2 | 已完成 | 多模型配置隔离 |
| Phase 6.3 | 已完成 | 课程问答流式输出 |
| Phase 6.4 | 已完成 | Embedding 与混合检索 |
| Phase 6.5 | 已完成 | 课程空间双模式前端改造 |
| Phase 7.1 | 已完成 | 真实学习画像、画像事件和课程问答画像候选事件 |
| Phase 7.2 | 已完成 | 学习事件语义与课程学习状态边界 |
| Phase 7.3 | 已完成 | 课程级弱点追踪与待确认复习队列第一刀 |
| Phase 7.4 | 已完成 | 课程级弱点复习队列确认与状态流转 |
| Phase 8.1 | 已完成 | Agent Graph 与可观测轨迹底座 |
| Phase 8.2 | 已完成 | 多智能体生成 5 类学习资源 |
| Phase 8.2.1 | 已完成 | 模型无关的资源质量收口，确定性可用稿优先、模型批量增强和规则质量分 |
| Phase 9 | 已完成 | 课程级学习路径、规则掌握度图、弱点队列推荐资源和复习时间 |
| Phase 10 | 已完成 | 练习生成、确定性批改、弱点/掌握度反哺和学习报告展示第一刀 |

## 下一步建议

当前可以继续进入 **Phase 11：期末冲刺和资料对比**。

原因：

- Phase 7 已完成用户级画像、画像事件和课程问答候选证据闭环。
- Phase 8 已完成资源生成和可观测底座，Phase 9 已把课程级路径、掌握度、弱点推荐资源和复习时间接入。
- Phase 10 已把真实练习、答题结果、弱点队列、掌握度修正和学习报告接入最小闭环。
- 下一步可基于课程资料、弱点、路径、练习和资源，做期末冲刺计划与资料对比，不需要再造一套画像或通用学习事件表。

可选并行方向：

- PDF/PPTX/DOCX 深度解析专项。
- 学习报告 Markdown 导出。
- 演示模式初始化与重置。

建议 Phase 11 只推进期末冲刺和资料对比的可演示第一刀，不同时展开报告文件导出或演示模式重置；继续保持代码、测试、文档和浏览器验收同步。
