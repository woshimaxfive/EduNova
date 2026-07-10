# EduNova 当前状态

更新时间：2026-07-10

## 状态摘要

当前最新完成到 **Phase 13.2：资料解析、主页智能工具和异步导出增强**。

Phase 计划继续以 `docs/superpowers` 原始实施计划为准。Phase 7 已按“对话式学习画像”主线收口；Phase 7.3 和 Phase 7.4 前置补齐课程级弱点队列基础，是为了让画像证据能落到课程状态里，不改变后续 Phase 编号。Phase 8 已完成 Agent 可观测底座、5 类课程资源生成和资源质量收口；Phase 9 已完成课程级学习路径、规则掌握度图、弱点队列推荐资源和复习时间第一版；Phase 10 已完成真实练习生成、确定性批改、弱点/掌握度反哺和学习报告展示第一刀；Phase 11.1 已完成课程级期末冲刺计划第一刀；Phase 11.2 已完成同课程多资料对比第一刀；Phase 12.1 已完成课程级 Markdown 学习档案导出第一刀；Phase 12.2 已把当前版本整理为可启动、可演示、可回归、可继续打磨的交付基线；Phase 13.1 已补 Agent trace 和工作流口径；Phase 13.2 已补齐 PDF/DOCX/PPTX 文本解析、主页联网搜索/深度思考/浏览器语音和 Markdown/PDF/DOCX 异步学习档案导出；2026-07-10 的 LangGraph hardening 已让 `HomeTutorGraph`、`CourseTutorGraph` 和 `ResourceGenerationGraph` 三条主链路真接管生产流程。

2026-07-10 已完成 Phase 13 前端视觉硬化第一轮：补齐前端语义化颜色、文字、阴影、圆角、等宽字体和焦点 token；统一运行时品牌色；登录页修正标题换行和表单层级；主页降低大标题与 pill 模板感并为 composer 增加可见焦点；课程空间把返回入口、A3 课程摘要、指标和 8 步轨重新分层；所有受保护路由在紧凑视口默认显示顶部导航条，展开后使用覆盖式侧栏抽屉，不再把完整桌面侧栏堆到页面底部。该轮不新增接口、数据表或学习能力。

2026-07-10 主页智能对话 hardening 已完成 `HomeTutorGraph` 真接管：新增 `material_chunks` 资料级 RAG，主页不再固定读取资料开头；home/course 共用 SSE，主页可展示安全状态、真实来源、增量 Markdown 和 Review 修订替换；回答通过输出边界、规则审核、模型 ReviewAgent 和单次 Repair 防止内部 Prompt 回显。主页允许模型通用知识，课程空间仍保持只能依据课程资料的严格 RAG。

该轮已通过 Docker 真实 PostgreSQL/pgvector 和 `agent-browser` 验收：选择“人工智能导论内置课程包.md”询问“什么是机器学习”能命中机器学习相关片段并输出正常 Markdown，联网未配置 warning 只出现在来源/轨迹区；连续追问 trace 显示最近 4 条会话上下文。验收中修复了弱模型 Review JSON 自相矛盾导致正常回答被误杀、中文整句相关性规则误判，以及 390px 长会话把输入框推到文档底部的问题。桌面和 390px 均为内部内容滚动、输入框固定可见、无水平溢出。

这一阶段之后，EduNova 已经从前端骨架推进到真实学生学习底座：

- 账号、首页、资料库、规则建课、课程知识库和课程会话都已经接入真实后端。
- 课程空间可以基于当前用户课程资料检索引用。
- 命中引用后可以调用当前用户默认模型配置生成回答。
- 课程回答支持 SSE 流式输出，完成后持久化消息、引用和 `trace_id`。
- RAG 检索已经从纯关键词升级到关键词 + 1536 维向量混合召回。
- 主页会话已经从固定模板回复改为调用当前用户默认模型生成通用回答。
- 主页会话通过 `HomeTutorGraph` 按需读取已选资料相关切片、Tavily-compatible 联网结果和安全深度规划，并展示真实 `home_tutor` trace；未配置搜索 Key 时 warning 进入来源/轨迹区，不伪造网页来源。
- 主页回答已支持 SSE 增量 Markdown、Graph 安全状态、`sources` 和 Review `replace`；失败时保留输入和已有历史，不持久化半截消息。
- 主页会话和课程空间会话已补齐同一 `session_id` 内多轮上下文：模型输入会带入最近 12 条安全历史和必要摘要，安全摘要合并到唯一的 system 指令以兼容 OpenAI-compatible 网关，课程 RAG 与主页联网搜索会用上下文化 query 处理追问，不存在 6 轮或 12 条消息的人工发送上限。
- 主页历史和课程空间历史支持会话菜单改名与软删除；删除当前会话后分别回到主页默认入口或课程问答引导态。
- 主页语音输入和回答朗读使用浏览器 Web Speech API，不做服务端音频上传或 STT。
- 课程空间已经从常驻面板页改为 A3 个性化学习闭环主场 + 默认问答模式 + 按需学习模式；登录后首页 `/app` 继续保持轻量入口，不改成驾驶舱。
- 学习画像已从前端骨架推进为真实后端画像、画像事件和课程问答画像候选事件。
- Phase 7.2 已明确用户级画像和课程级学习状态的边界：用户级画像只有一份，课程级目标、薄弱点、掌握度、复习队列和学习路径按课程聚合。
- Phase 7.3 已把课程问答弱点候选事件同步为课程级 `weakness_review_queue` 待确认复习项，并在课程空间展示真实“待复习弱点”摘要。
- Phase 7.4 已为课程级弱点复习项补齐确认、开始、完成和软忽略状态流转，课程空间可以直接操作真实队列项。
- 2026-07-10 LangGraph hardening 已让 `HomeTutorGraph`、`CourseTutorGraph` 和 `ResourceGenerationGraph` 真接管三条生产主链路；路径、练习、报告和导出仍保留现有服务逻辑和轻量 `agent_trace_id`，后续再图化。
- Phase 8.2 已挂载 `/resources`，可基于当前用户课程生成讲解、思维导图、练习、代码实操和 PPT 大纲，并写入资源、质量分和 Agent 轨迹；Phase 8.2.1 已改为课程引用驱动的确定性可用稿优先，模型只做批量增强，模型不可用或失败时不再把可用资源降级为空模板。
- Phase 9 已挂载 `/paths`，可为当前用户课程生成 active 学习路径、更新任务状态，并把 `/app/path` 接入真实课程、任务、路径依据和掌握度图。
- Phase 9 已实现 `/courses/{course_id}/mastery-map`，并让 `/courses/{course_id}/learning-state` 返回真实路径摘要、掌握度摘要、弱点推荐资源和下次复习时间。
- Phase 10 已挂载 `/practice` 和 `/reports`，可创建课程练习、提交作答、确定性批改、把错题或低分题写入 `practice_assessment` 来源的 `confirmed` 弱点，并生成/读取课程学习报告。
- Phase 11.1 已挂载 `/exam-sprint`，可基于课程知识点、已确认/复习中弱点、练习低分、资源和报告建议生成 3/7/14 天课程级期末冲刺计划，并在 `/app/path` 展示冲刺任务、高频点、薄弱点、必刷题、易错提醒和推荐资源。
- Phase 11.2 已挂载 `/materials/compare`，可对同一课程下 2 份以上已绑定资料做确定性对比，输出重复重点、疑似考点、单资料独有点、试题独有点、遗漏复习点、优先复习顺序和安全引用，并在 `/app/library` 展示。
- Phase 12.1 已挂载 `/exports/learning-dossier`，可同步导出当前用户课程级 Markdown 学习档案；Phase 13.2 已挂载 `/exports/learning-dossier/jobs`、`/exports/{job_id}` 和 `/exports/{job_id}/download`，可通过 Redis/RQ worker 异步生成 Markdown/PDF/DOCX 学习档案，并在 `/app/reports` 选择格式下载。
- Phase 12.2 已补齐交付基线文档、开源说明、MIT 许可证、用户指南、答辩问答、测试报告和验收证据索引。

2026-07-10 后，LangGraph 不再只是可观测骨架：主页问答、课程问答和资源生成已经由真实 Graph runner 编排并落 `agent_run_logs`；画像、资料建课/对比、路径/冲刺、练习评估、学习报告和学习档案导出仍使用现有服务逻辑与兼容 trace，后续逐步接管。认证、设置、Dashboard 等非学习能力仍保持普通服务。

当前仍然不是完整商业产品。课程级路径、掌握度图、弱点队列、练习评估、学习报告、期末冲刺、资料对比、PDF/DOCX/PPTX 文本解析和 Markdown/PDF/DOCX 学习档案导出已经接入，交付基线文档和开源准备已补齐；但错题驱动的深度薄弱点追溯、资料对比与期末冲刺联动、OCR、旧版 Office 解析、扫描件解析和完整浏览器 E2E 还在后续打磨阶段。快速演示入口按注册页“带一个示例课程开始”处理，不再新增共享演示账号重置作为当前主线。

## 已完成主链路

| 范围 | 当前能力 | 关键入口 |
| --- | --- | --- |
| 认证 | 注册、登录、读取当前用户、退出、受保护路由 | `/api/v1/auth/*` |
| 首页总览 | 当前用户课程、资料、主页历史和空状态 | `/api/v1/dashboard/summary` |
| 主页会话 | `HomeTutorGraph`、资料级 RAG、联网/深度规划、SSE Markdown、Review/Repair、连续追问、历史切换、改名、软删除和刷新保留 | `/api/v1/tutor/sessions` |
| 资料库 | 上传、列表、详情、解析进度、课程关联和同课程资料对比 | `/api/v1/materials/*` |
| 规则建课 | 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料生成课程、知识点和切片 | `/api/v1/courses/from-materials` |
| 课程详情 | 课程列表、详情、概览、知识点 | `/api/v1/courses/*` |
| RAG 检索 | 当前用户课程内关键词/向量混合检索 | `/api/v1/rag/search` |
| 课程会话 | 课程内历史、消息、引用持久化、历史改名、软删除和刷新恢复 | `/api/v1/tutor/sessions?scope=course` |
| 模型设置 | 多套个人模型配置、默认配置、连接测试、服务器兜底 | `/api/v1/settings/model/configs` |
| 账号设置 | 当前用户昵称真实保存并同步侧栏账号入口 | `PATCH /api/v1/auth/me` |
| 课程回答 | `CourseTutorGraph` 接管非流式与流式课程 RAG 回答 | `/messages`、`/messages/stream` |
| Embedding | OpenAI-compatible `/embeddings` 与本地 fallback | `EmbeddingService` |
| 学习画像 | 8 维用户级画像、画像对话更新、画像事件、课程问答候选事件和课程状态分层边界 | `/api/v1/profiles/*` |
| 课程学习状态 | 当前课程画像叠层、弱点候选计数、复习队列和状态流转 | `/api/v1/courses/{course_id}/learning-state` |
| Agent 轨迹 | 当前用户自己的 Agent trace 查询、步骤排序、Graph 工作流和安全摘要返回 | `/api/v1/agents/traces/{trace_id}` |
| 课程资源 | `ResourceGenerationGraph` 接管 5 类课程学习资源、质量分和 trace | `/api/v1/resources/*` |
| 学习路径 | 生成课程级 active 路径、更新路径任务、读取当前路径 | `/api/v1/paths/*` |
| 掌握度图 | 按课程知识点、弱点队列、路径任务、资源推荐和练习结果计算规则掌握度 | `/api/v1/courses/{course_id}/mastery-map` |
| 练习评估 | 创建课程练习、提交作答、确定性批改并反哺弱点队列 | `/api/v1/practice/*` |
| 学习报告 | 基于课程、练习、掌握度和弱点生成真实报告 | `/api/v1/reports/*` |
| 学习档案导出 | 同步 Markdown 兼容接口与 Markdown/PDF/DOCX 异步导出任务 | `/api/v1/exports/*` |
| 期末冲刺 | 生成 3/7/14 天课程级冲刺计划、每日任务、高频点、必刷题和易错提醒 | `/api/v1/exam-sprint/*` |
| 资料对比 | 同课程多资料重复重点、疑似考点、独有点、遗漏点和安全引用 | `/api/v1/materials/compare` |
| 交付基线 | 开源说明、开发指南、测试报告、用户指南、答辩问答、MIT 许可证和验收证据索引 | `docs/*`、`LICENSE` |

## 当前前端状态

| 页面 | 当前状态 |
| --- | --- |
| `/login` | 调用真实登录接口，不提供共享演示学生按钮 |
| `/register` | 调用真实注册接口，可选择空白开始或复制人工智能导论 |
| `/app` | GPT 式主页，真实读取 summary、主页历史、最近课程和资料库浮层；发送后流式消费 `HomeTutorGraph` 状态、来源、Markdown token 和 Review 替换，可附加已选资料级 RAG、联网、深度规划和多轮上下文；支持语音输入、朗读、历史改名和删除 |
| `/app/library` | 文件库式资料库，真实读取资料列表，支持上传、搜索、筛选、详情和同课程资料对比 |
| `/app/courses/:courseId` | A3 个性化学习闭环主场 + 默认问答模式 + 按需学习模式；读取真实课程、知识点、课程历史、消息、引用、课程学习状态、课程资源、当前路径、最新报告和课堂协作轨迹，支持带多轮上下文的流式课程问答、课程历史改名/删除、弱点队列操作、课程内 5 类资源生成，并带当前 `course_id` 进入路径、练习和报告 |
| `/app/settings` | 管理多套模型配置，支持 Provider 预设、保存、测试、设默认和删除 |
| `/app/studio` | 真实资源工坊，读取课程、知识点和当前用户资源，可生成 5 类课程资源并展示模型增强/本地可用稿/低依据、引用、质量分和 ResourceGenerationGraph 轨迹 |
| `/app/profile` | 读取真实 8 维画像、画像事件和画像对话更新；空画像显示待补充，不展示静态假画像 |
| `/app/tutor` | 课程辅导入口，读取当前用户课程并跳转对应课程空间，不再展示静态假问答 |
| `/app/practice` | 读取真实课程和知识点，创建课程练习、作答、提交并展示即时反馈和复习线索 |
| `/app/reports` | 读取真实课程和最新报告，可生成学习报告；展示真实分数、掌握度更新、薄弱点、证据摘要和下一步建议；可创建异步导出任务并下载 Markdown/PDF/DOCX 学习档案 |
| `/app/path` | 读取真实普通学习路径、掌握度图，并可生成当前课程 3/7/14 天期末冲刺计划 |

当前前端不再使用中间横向的 `ActionNotice` 提示。历史切换、筛选、开关和详情展开依靠选中态或内容变化表达；上传失败、发送失败、课程生成失败和表单校验错误使用局部提示；模型配置保存、测试、设默认和删除使用右下角轻量 toast。

主页输入区的资料状态只显示已选资料数量，并贴近底部输入框；联网搜索和深度思考会进入发送 payload，回答下方展示真实返回来源和 `home_tutor` trace。未配置搜索 Key 时只显示 warning，不伪造网页来源。

普通二级路由（资料库、资源工坊、画像、设置、路径、练习和报告等）复用左侧主页工作区侧栏，并读取 `/dashboard/summary` 的真实主页历史；从这些页面点击主页历史会回到 `/app` 并打开对应会话。课程空间仍显示当前课程内历史，不混入主页历史。

Phase 13 前端视觉硬化后，桌面端继续保留 264px / 68px 的展开与收起侧栏；`900px` 及以下视口默认收起为 58px 顶部导航条，点击后以覆盖式抽屉显示完整导航、历史和账号入口。移动端导航动作完成后自动收起抽屉。`/app`、普通 `PageFrame` 路由和课程空间复用同一响应式状态逻辑；键盘焦点统一使用可见青绿色焦点环，composer 使用 `:focus-within` 显示输入焦点。

课程空间 Phase 6.5 已落地“默认问答模式 + 按需学习模式”。2026-07-07 的 A3 闭环打磨进一步把 `/app/courses/:courseId` 定位为个性化学习闭环主场：顶部展示当前目标、依据、下一步和画像、检索、辅导、弱点、资源、路径、评估、报告步骤流；默认问答模式保持课程版 ChatGPT 体验，真实引用、课程内 5 类资源生成、学习路径、练习、报告和课堂协作轨迹在回答下方渐进展开；知识点不再以横向列表常驻首屏，而是通过轻量入口进入学习模式后选择，引用来源可直接进入学习模式。学习模式中间显示学习内容，右侧提供上下文 AI 辅导。“课堂协作轨迹”会在存在 `latest_trace_id` 时读取真实 `CourseTutorGraph` trace，并只展示“已参考最近 N 条会话”等安全上下文提示；课程行动入口带 `course_id` 跳转 `/app/path`、`/app/practice` 和 `/app/reports`。

## 当前后端状态

| 模块 | 当前状态 |
| --- | --- |
| FastAPI 应用 | 已有 `/api/health` 和 `/api/v1` 路由结构 |
| 数据库 | PostgreSQL + pgvector，Alembic 迁移到当前 head |
| 课程包 | 人工智能导论内置课程包可幂等导入 |
| 认证 | bcrypt、JWT、`starter_mode` 和当前用户依赖已接入 |
| 资料库 | 独立 `materials`、`material_chunks` 和 `course_material_links` 已接入；PDF/DOCX/PPTX 文本解析、主页资料级混合检索已接入，图片/扫描件不做 OCR；Phase 11.2 已接同课程资料对比 |
| 课程 | TXT/Markdown/PDF/DOCX/PPTX 已解析资料规则建课、课程学习状态、待确认弱点队列同步和状态流转已接入 |
| RAG | 混合检索、引用字段和检索状态已接入 |
| 模型 | OpenAI-compatible chat、stream、embeddings 已接入 |
| 学习画像 | `profiles` router 已接入，复用 `student_profiles` 和 `profile_events`；不为每门课复制完整画像 |
| Agent 轨迹 | `agents` router 已接入，复用 `agent_run_logs`，支持当前用户 trace 查询、Graph 工作流字段和安全摘要返回 |
| 课程资源 | `resources` router 已接入，复用 `generated_resources`、`resource_quality_scores` 和 `agent_run_logs`，支持 5 类课程资源同步生成 |
| 学习路径 | `paths` router 已接入，复用 `learning_paths` 和 `learning_tasks`，支持课程级路径生成和任务状态更新 |
| 练习评估 | `practice` router 已接入，复用 `practice_sessions`、`practice_answers` 和 `weakness_review_queue`，支持确定性出题、批改和弱点反哺 |
| 学习报告 | `reports` router 已接入，复用 `assessment_reports`，支持课程最新报告读取和报告生成 |
| 学习档案导出 | `exports` router 已接入，旧接口同步生成 Markdown；`export_jobs` + Redis/RQ worker 支持 Markdown/PDF/DOCX 异步文件导出和下载 |
| 期末冲刺 | `exam_sprint` router 已接入，复用 `learning_paths` 和 `learning_tasks`，支持课程级冲刺计划生成和读取 |
| Docker | Compose 六服务可按默认端口启动，包含 PostgreSQL、Redis、backend、export-worker、frontend、nginx；backend 与 worker 共享导出卷 |
| 安全 | 用户数据隔离、Key 加密、脱敏返回和上传目录忽略已接入 |

当前后端已挂载的业务 router 是 `auth`、`dashboard`、`courses`、`materials`、`profiles`、`rag`、`settings`、`tutor`、`agents`、`resources`、`paths`、`practice`、`reports`、`exam_sprint` 和 `exports`。`demo` 仍只是前端 API 常量与后续接口设计，不属于当前已实现后端能力。

资源分层口径：`generated_resources.course_id != null` 是课程资源，Phase 8.2 只生成这一类；`course_id == null` 预留为后续个人全局资源，本阶段不提供生成入口。资源生成在 Phase 8.2.1 后固定为“确定性可用稿优先，模型批量增强”：本地 draft 先保证 5 类资源具备可读、可练、可复用结构，模型未配置、调用失败、解析失败、输出缺失或输出含敏感标记时保留对应资源的本地可用稿。`content_json.metadata.generation_mode` 区分 `model_enhanced`、`deterministic_source` 和 `low_evidence_fallback`；`review_status="passed"` 表示资源通过本地质量门槛，不要求一定来自模型，`low_evidence` 只表示课程依据不足。资源、质量分和 Agent trace 均不保存系统提示词、完整模型输入、API Key、完整课程资料原文或完整用户画像原文。

课程问答在 Phase 7.1 后会把明确困惑/薄弱信号沉淀为画像候选事件，但只保存课程、会话、消息、`trace_id` 和引用摘要，不保存完整用户问题、系统提示词、模型输入或资料原文。Phase 7.3 的 `/courses/{course_id}/learning-state` 会把当前课程的这些候选事件按知识点或安全标题同步为 `pending` 待确认复习项，不把候选事件直接宣称为已诊断弱点。Phase 7.4 后，学生可以把队列项确认为 `confirmed`、开始为 `reviewing`、完成为 `completed`，也可以软忽略为 `dismissed`；`dismissed` 不在主列表展示，但继续参与去重。

Phase 7.2 的分层口径：

- `student_profiles` 保存用户级长期画像，只保留一份。
- `profile_events` 保存证据流，可带课程来源信息。
- `weakness_review_queue` 保存课程级可执行复习项，Phase 7.3 已接入课程问答候选事件到 `pending` 项的同步，Phase 7.4 已接入确认、开始、完成和软忽略状态流转，必须绑定 `course_id`。
- `learning_paths` 和 `learning_tasks` 保存 Phase 9 生成的课程级 active 路径和任务，旧 active 路径会归档为 `archived`。
- Phase 11.1 期末冲刺同样复用 `learning_paths` 和 `learning_tasks`，但使用 `sprint_active` / `sprint_archived` 和 `plan_json.kind="exam_sprint"`，不会影响普通 `active` 学习路径。
- `/courses/{course_id}/learning-state` 是课程级学习状态聚合接口，不新增通用 `learning_events` 表；Phase 9 后同时返回路径摘要、掌握度摘要、推荐资源和复习时间，Phase 10 后练习结果会反哺掌握度和 `practice_assessment` 来源弱点。

课程空间和普通二级路由已经去掉前端 demo 数据兜底：真实课程加载中不会显示“人工智能导论”示例课程，资源工坊初始不展示假生成队列，报告页不展示固定资料证据，普通二级路由侧栏不再注入主页 demo 历史，而是复用真实主页历史并回到 `/app` 打开会话。

## 尚未完成

| 能力 | 当前处理 |
| --- | --- |
| OCR 和图片题目识别 | 图片只入库，不做识别；扫描件 PDF 不伪装 OCR |
| 旧版 Office 解析 | `.doc`、`.ppt` 只入库，不做深度解析 |
| 讯飞原生 Embeddingp/Embeddingq | 暂不接入，当前用 OpenAI-compatible embeddings 或本地 fallback |
| 资料对比增强 | Phase 11.2 已接入第一刀；结果持久化、与期末冲刺联动和跨资料原文对照页未接入 |
| 资源增强 | Phase 8.2.1 已支持 5 类课程资源的模型无关可用稿、可选模型增强和规则质量分；资源编辑、异步任务队列、个人全局资源生成入口和推荐资源消费未接入 |
| Agent 编排 hardening | `CourseTutorGraph` 和 `ResourceGenerationGraph` 已真接管生产流程；其他闭环 Graph 仍是后续专项，继续补浏览器 E2E 和更多白名单 metadata 打磨 |
| 弱点复习增强 | Phase 10 已接入练习评估来源；错题驱动的更细粒度追溯、队列项编辑和练习再推荐未接入 |
| 学习路径 | Phase 9 已接入真实路径生成、当前路径读取、任务状态更新和课程页摘要 |
| 掌握度图 | Phase 10 已接入练习评估修正；仍是规则计算，不单独持久化 |
| 学习报告导出 | Phase 13.2 已接入 Markdown/PDF/DOCX 异步导出；后续可继续打磨版式和下载体验 |
| 独立演示模式重置 | 当前快速演示通过注册页示例课程进入；共享演示账号重置不作为当前主线 |

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
| Phase 11.1 | 已完成 | 期末冲刺模式第一刀，课程级 3/7/14 天冲刺计划 |
| Phase 11.2 | 已完成 | 资料对比第一刀，同课程多资料重点、考点、遗漏点和安全引用 |
| Phase 12.1 | 已完成 | Markdown 学习档案导出第一刀，同步返回课程级学习档案并在报告页下载 |
| Phase 12.2 | 已完成 | 交付基线、开源准备、MIT 许可证、验收证据和提交前文档初版 |
| Phase 13.1 | 已完成 | 学习产物 trace 字段、Graph 工作流口径和前端轻量轨迹入口 |
| Phase 13.2 | 已完成 | PDF/DOCX/PPTX 资料解析、主页联网/深思/语音、Markdown/PDF/DOCX 异步学习档案导出 |
| Phase 13 hardening | 已完成 | `HomeTutorGraph`、`CourseTutorGraph` 和 `ResourceGenerationGraph` 三条主链路真接管生产流程 |

## 下一步建议

当前可以继续推进 **Phase 13：Verification and Hardening / 产品打磨**，重点从“能力是否接上”转为“Graph 轨迹、解析结果、导出版式和移动体验是否足够好看、好懂、可验收”。

原因：

- Phase 7 已完成用户级画像、画像事件和课程问答候选证据闭环。
- Phase 8 已完成资源生成和可观测底座，Phase 9 已把课程级路径、掌握度、弱点推荐资源和复习时间接入。
- Phase 10 已把真实练习、答题结果、弱点队列、掌握度修正和学习报告接入最小闭环。
- Phase 11.1 已把课程资料、弱点、路径、练习、资源和报告建议沉淀为可展示的期末冲刺计划。
- Phase 11.2 已把课程资料之间的重复重点、疑似考点、独有点、遗漏点和安全引用接入资料库，不需要再造资料对比持久化表。
- Phase 12.1 已把课程报告、弱点、路径、资源和练习证据聚合为可下载的 Markdown 学习档案；Phase 13.2 已在此基础上补齐 `export_jobs` 和 Markdown/PDF/DOCX 异步导出。
- Phase 12.2 已把开源说明、开发指南、测试报告、用户指南、答辩问答、AI 辅助开发说明、MIT 许可证和验收证据索引补齐。
- Phase 13 hardening 已把课程问答和资源生成从手写 trace 推进为真实 LangGraph runner；路径、冲刺、练习、报告和导出继续保留轻量 trace，等待后续专项。

可选并行方向：

- 资料对比结果与期末冲刺的后续联动。
- 导出文件版式、完整浏览器 E2E、课程空间移动体验继续打磨和验收中发现问题的 P0/P1 修复。

建议 Phase 13 继续做 Verification and Hardening，不同时展开 OCR 或旧版 Office 解析；继续保持代码、测试、文档和浏览器验收同步。
