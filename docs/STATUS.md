# EduNova 当前状态

更新时间：2026-07-10

## 状态摘要

当前最新完成到 **Phase 15：个性化根基与智能课程生产**。

Phase 计划继续以 `docs/superpowers` 原始实施计划为准。Phase 13 已完成主页问答、课程问答和资源生成的真实 Graph 编排，Phase 14 已让路径、练习评估和报告进入真实 LangGraph，Phase 15 已让画像和资料建课进入生产 Graph，并补齐个性化策略、学习连续性与前端可视化。

Phase 15 使用 Alembic `20260710_0012` 增加逐维画像可信度、课程 v2 结构和画像证据状态。`ProfileGraph` 支持显式画像回答和隐式学习信号，隐式信号只有通过双来源与置信度门槛才进入长期画像；`CourseBuilderGraph` 生成带真实来源覆盖、先修关系和审核摘要的课程结构，embedding 失败只降级关键词检索。练习支持 adaptive 难度、最近会话和草稿恢复；课程学习模式使用 React Flow，路径与报告使用 ECharts，同时保留可访问文本内容。

Phase 14 使用 Alembic `20260710_0011` 增加练习闭环证据字段。`AssessmentGraph` 保证客观分数由规则决定，错题精确关联 `PracticeAnswer` 并合并更新弱点；`PathPlanningGraph` 只重排已有路径并保留完成进度；`ReportGraph` 确定性聚合最近 5 次练习和趋势。模型只增强题目、诊断、路径理由和报告叙事，失败时明确使用 `rules_only`。课程 RAG 在外部 embedding 可用时使用 pgvector SQL cosine 候选，未配置或失败时退回关键词检索，不再把本地 hash 宣称为语义命中。

2026-07-10 已完成 Phase 13 前端视觉硬化第一轮：补齐前端语义化颜色、文字、阴影、圆角、等宽字体和焦点 token；统一运行时品牌色；登录页修正标题换行和表单层级；主页降低大标题与 pill 模板感并为 composer 增加可见焦点；课程空间把返回入口、A3 课程摘要、指标和 8 步轨重新分层；所有受保护路由在紧凑视口默认显示顶部导航条，展开后使用覆盖式侧栏抽屉，不再把完整桌面侧栏堆到页面底部。该轮不新增接口、数据表或学习能力。

2026-07-10 主页智能对话 hardening 已完成 `HomeTutorGraph` 真接管：新增 `material_chunks` 资料级 RAG，主页不再固定读取资料开头；home/course 共用 SSE，主页可展示安全状态、真实来源、增量 Markdown 和 Review 修订替换；回答通过输出边界、规则审核、模型 ReviewAgent 和单次 Repair 防止内部 Prompt 回显。主页允许模型通用知识，课程空间仍保持只能依据课程资料的严格 RAG。

该轮已通过 Docker 真实 PostgreSQL/pgvector 和 `agent-browser` 验收：选择“人工智能导论内置课程包.md”询问“什么是机器学习”能命中机器学习相关片段并输出正常 Markdown，联网未配置 warning 只出现在来源/轨迹区；连续追问 trace 显示最近 4 条会话上下文。验收中修复了弱模型 Review JSON 自相矛盾导致正常回答被误杀、中文整句相关性规则误判，以及 390px 长会话把输入框推到文档底部的问题。桌面和 390px 均为内部内容滚动、输入框固定可见、无水平溢出。

这一阶段之后，EduNova 已经从前端骨架推进到真实学生学习底座：

- 账号、首页、资料库、智能建课、课程知识库和课程会话都已经接入真实后端。
- 课程空间可以基于当前用户课程资料检索引用。
- 命中引用后可以调用当前用户默认模型配置生成回答。
- 课程回答支持 SSE 流式输出，完成后持久化消息、引用和 `trace_id`。
- RAG 检索在真实外部 1536 维 embedding 可用时融合 pgvector SQL cosine 候选与关键词候选；本地 hash 和 Provider 失败只走关键词 fallback。
- 主页会话已经从固定模板回复改为调用当前用户默认模型生成通用回答。
- 主页会话通过 `HomeTutorGraph` 按需读取已选资料相关切片、Tavily-compatible 联网结果和安全深度规划，并展示真实 `home_tutor` trace；未配置搜索 Key 时 warning 进入来源/轨迹区，不伪造网页来源。
- 主页回答已支持 SSE 增量 Markdown、Graph 安全状态、`sources` 和 Review `replace`；失败时保留输入和已有历史，不持久化半截消息。
- 主页会话和课程空间会话已补齐同一 `session_id` 内多轮上下文：模型输入会带入最近 12 条安全历史和必要摘要，安全摘要合并到唯一的 system 指令以兼容 OpenAI-compatible 网关，课程 RAG 与主页联网搜索会用上下文化 query 处理追问，不存在 6 轮或 12 条消息的人工发送上限。
- 主页历史和课程空间历史支持会话菜单改名与软删除；删除当前会话后分别回到主页默认入口或课程问答引导态。
- 主页语音输入和回答朗读使用浏览器 Web Speech API，不做服务端音频上传或 STT。
- 课程空间已经从常驻面板页改为 A3 个性化学习闭环主场 + 默认问答模式 + 按需学习模式；登录后首页 `/app` 继续保持轻量入口，不改成驾驶舱。
- 学习画像已由 `ProfileGraph` 接管，画像页展示逐维可信度、候选/已应用证据和真实轨迹。
- Phase 7.2 已明确用户级画像和课程级学习状态的边界：用户级画像只有一份，课程级目标、薄弱点、掌握度、复习队列和学习路径按课程聚合。
- Phase 7.3 已把课程问答弱点候选事件同步为课程级 `weakness_review_queue` 待确认复习项，并在课程空间展示真实“待复习弱点”摘要。
- Phase 7.4 已为课程级弱点复习项补齐确认、开始、完成和软忽略状态流转，课程空间可以直接操作真实队列项。
- 2026-07-10 Phase 15 后，`ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph` 和 `ReportGraph` 已真接管八条生产主链路；资料对比、期末冲刺和导出仍保留现有服务逻辑与兼容 trace。
- `/resources` 可基于当前用户课程生成讲解、思维导图、练习、代码实操、PPT 和动画图解。六个 Worker 分别执行模型增强并保留确定性 fallback，ReviewAgent 结合结构规则和模型审核，失败资源最多修订一次；旧 Markdown 资源继续兼容读取。
- Phase 9 已挂载 `/paths`，可为当前用户课程生成 active 学习路径、更新任务状态，并把 `/app/path` 接入真实课程、任务、路径依据和掌握度图。
- Phase 9 已实现 `/courses/{course_id}/mastery-map`，并让 `/courses/{course_id}/learning-state` 返回真实路径摘要、掌握度摘要、弱点推荐资源和下次复习时间。
- Phase 14 已将 `/practice` 和 `/reports` 升级为真实 Graph：练习创建/提交保留确定性分数并生成错因诊断，错题与弱点证据精确绑定，已有路径自动重排；报告聚合最近 5 次练习并展示规则趋势、证据摘要和真实轨迹。
- Phase 11.1 已挂载 `/exam-sprint`，可基于课程知识点、已确认/复习中弱点、练习低分、资源和报告建议生成 3/7/14 天课程级期末冲刺计划，并在 `/app/path` 展示冲刺任务、高频点、薄弱点、必刷题、易错提醒和推荐资源。
- Phase 11.2 已挂载 `/materials/compare`，可对同一课程下 2 份以上已绑定资料做确定性对比，输出重复重点、疑似考点、单资料独有点、试题独有点、遗漏复习点、优先复习顺序和安全引用，并在 `/app/library` 展示。
- Phase 12.1 已挂载 `/exports/learning-dossier`，可同步导出当前用户课程级 Markdown 学习档案；Phase 13.2 已挂载 `/exports/learning-dossier/jobs`、`/exports/{job_id}` 和 `/exports/{job_id}/download`，可通过 Redis/RQ worker 异步生成 Markdown/PDF/DOCX 学习档案，并在 `/app/reports` 选择格式下载。
- Phase 12.2 已补齐交付基线文档、开源说明、MIT 许可证、用户指南、答辩问答、测试报告和验收证据索引。

2026-07-10 后，八条主链路已经由真实 Graph runner 编排并落 `agent_run_logs`：动态画像、智能建课、主页问答、课程问答、资源生成、学习路径、练习评估和学习报告。资料对比、期末冲刺和学习档案导出仍使用现有服务逻辑与兼容 trace。认证、设置、Dashboard 等非学习能力保持普通服务。

当前仍然不是完整商业产品。课程级路径、错题诊断与回流、掌握度、学习报告、期末冲刺、资料对比、资料解析、学习档案导出和隔离 Docker E2E 已接入；但资料对比与期末冲刺联动、OCR、旧版 Office、扫描件解析，以及剩余学习流程的真实 Graph 接管仍在后续阶段。

## 已完成主链路

| 范围 | 当前能力 | 关键入口 |
| --- | --- | --- |
| 认证 | 注册、登录、读取当前用户、退出、受保护路由 | `/api/v1/auth/*` |
| 首页总览 | 当前用户课程、资料、主页历史和空状态 | `/api/v1/dashboard/summary` |
| 主页会话 | `HomeTutorGraph`、资料级 RAG、联网/深度规划、SSE Markdown、Review/Repair、连续追问、历史切换、改名、软删除和刷新保留 | `/api/v1/tutor/sessions` |
| 资料库 | 上传、列表、详情、解析进度、课程关联和同课程资料对比 | `/api/v1/materials/*` |
| 智能建课 | `CourseBuilderGraph` 从已解析 TXT/Markdown/PDF/DOCX/PPTX 资料生成 v2 课程结构、知识点、先修关系和来源切片 | `/api/v1/courses/from-materials` |
| 课程详情 | 课程列表、详情、概览、知识点 | `/api/v1/courses/*` |
| RAG 检索 | 外部 embedding + pgvector SQL 与关键词混合；本地关键词 fallback | `/api/v1/rag/search` |
| 课程会话 | 课程内历史、消息、引用持久化、历史改名、软删除和刷新恢复 | `/api/v1/tutor/sessions?scope=course` |
| 模型设置 | 多套个人模型配置、默认配置、连接测试、服务器兜底 | `/api/v1/settings/model/configs` |
| 账号设置 | 当前用户昵称真实保存并同步侧栏账号入口 | `PATCH /api/v1/auth/me` |
| 课程回答 | `CourseTutorGraph` 接管非流式与流式课程 RAG 回答 | `/messages`、`/messages/stream` |
| Embedding | OpenAI-compatible `/embeddings`；本地 hash 仅标记关键词 fallback | `EmbeddingService` |
| 学习画像 | `ProfileGraph` 管理 8 维用户级画像、逐维可信度、候选/已应用证据和学习信号门控 | `/api/v1/profiles/*` |
| 课程学习状态 | 当前课程画像叠层、弱点候选计数、复习队列和状态流转 | `/api/v1/courses/{course_id}/learning-state` |
| Agent 轨迹 | 当前用户自己的 Agent trace 查询、步骤排序、Graph 工作流和安全摘要返回 | `/api/v1/agents/traces/{trace_id}` |
| 课程资源 | `ResourceGenerationGraph` 接管六类结构化资源、质量审核、PPTX 导出和 trace | `/api/v1/resources/*` |
| 学习路径 | `PathPlanningGraph` 生成/重排 active 路径并保留进度 | `/api/v1/paths/*` |
| 掌握度图 | 按课程知识点、弱点队列、路径任务、资源推荐和练习结果计算规则掌握度 | `/api/v1/courses/{course_id}/mastery-map` |
| 练习评估 | `AssessmentGraph` 出题、确定性评分、错因诊断、弱点与路径回流 | `/api/v1/practice/*` |
| 学习报告 | `ReportGraph` 聚合最近练习、掌握度、弱点、路径、资源与趋势 | `/api/v1/reports/*` |
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
| `/app/courses/:courseId` | A3 个性化学习闭环主场；支持流式课程问答、React Flow 知识先修图、弱点队列、六类资源与闭环入口 |
| `/app/settings` | 管理多套模型配置，支持 Provider 预设、保存、测试、设默认和删除 |
| `/app/studio` | 真实资源工坊，可生成并渲染六类结构化资源，展示引用、质量分、Graph 轨迹和 PPTX 导出状态 |
| `/app/profile` | 读取真实 8 维画像、逐维可信度、候选/已应用证据和 ProfileGraph 轨迹 |
| `/app/tutor` | 课程辅导入口，读取当前用户课程并跳转对应课程空间，不再展示静态假问答 |
| `/app/practice` | 支持 adaptive 难度、最近练习/草稿恢复、确定性评分、诊断和路径回流 |
| `/app/reports` | 读取真实课程和最新报告，可生成学习报告；展示真实分数、掌握度更新、薄弱点、证据摘要和下一步建议；可创建异步导出任务并下载 Markdown/PDF/DOCX 学习档案 |
| `/app/path` | 读取真实普通学习路径、掌握度图，并可生成当前课程 3/7/14 天期末冲刺计划 |

当前前端不再使用中间横向的 `ActionNotice` 提示。历史切换、筛选、开关和详情展开依靠选中态或内容变化表达；上传失败、发送失败、课程生成失败和表单校验错误使用局部提示；模型配置保存、测试、设默认和删除使用右下角轻量 toast。

主页输入区的资料状态只显示已选资料数量，并贴近底部输入框；联网搜索和深度思考会进入发送 payload，回答下方展示真实返回来源和 `home_tutor` trace。未配置搜索 Key 时只显示 warning，不伪造网页来源。

普通二级路由（资料库、资源工坊、画像、设置、路径、练习和报告等）复用左侧主页工作区侧栏，并读取 `/dashboard/summary` 的真实主页历史；从这些页面点击主页历史会回到 `/app` 并打开对应会话。课程空间仍显示当前课程内历史，不混入主页历史。

Phase 13 前端视觉硬化后，桌面端继续保留 264px / 68px 的展开与收起侧栏；`900px` 及以下视口默认收起为 58px 顶部导航条，点击后以覆盖式抽屉显示完整导航、历史和账号入口。移动端导航动作完成后自动收起抽屉。`/app`、普通 `PageFrame` 路由和课程空间复用同一响应式状态逻辑；键盘焦点统一使用可见青绿色焦点环，composer 使用 `:focus-within` 显示输入焦点。

课程空间采用“默认问答模式 + 按需学习模式”，并作为 A3 闭环主场展示目标、依据、下一步和学习步骤流。真实引用、六类结构化资源、路径、练习、报告和协作轨迹在回答下方渐进展开；资源生成后可直接切换并内联预览，资源工坊继续作为成果库。轨迹只展示安全摘要，不展示原始思维链。

## 当前后端状态

| 模块 | 当前状态 |
| --- | --- |
| FastAPI 应用 | 已有 `/api/health` 和 `/api/v1` 路由结构 |
| 数据库 | PostgreSQL + pgvector，Alembic 迁移到当前 head |
| 课程包 | 人工智能导论内置课程包可幂等导入 |
| 认证 | bcrypt、JWT、`starter_mode` 和当前用户依赖已接入 |
| 资料库 | 独立 `materials`、`material_chunks` 和 `course_material_links` 已接入；PDF/DOCX/PPTX 文本解析、主页资料级混合检索已接入，图片/扫描件不做 OCR；Phase 11.2 已接同课程资料对比 |
| 课程 | `CourseBuilderGraph` 智能建课、v2 课程结构、来源覆盖、先修关系和课程学习状态已接入 |
| RAG | 混合检索、引用字段和检索状态已接入 |
| 模型 | OpenAI-compatible chat、stream、embeddings 已接入 |
| 学习画像 | `ProfileGraph` 已接入显式/隐式更新、证据门控、Review/Repair 和逐维可信度；不为每门课复制完整画像 |
| Agent 轨迹 | `agents` router 已接入，复用 `agent_run_logs`，支持当前用户 trace 查询、Graph 工作流字段和安全摘要返回 |
| 课程资源 | `resources` router 已接入，支持六类 v2 结构化资源、并行 Worker、真实审核、旧资源兼容和 PPTX 异步导出 |
| 学习路径 | `paths` router 已接入，复用 `learning_paths` 和 `learning_tasks`，支持课程级路径生成和任务状态更新 |
| 练习评估 | `practice` router 已接入，复用 `practice_sessions`、`practice_answers` 和 `weakness_review_queue`，支持确定性出题、批改和弱点反哺 |
| 学习报告 | `reports` router 已接入，复用 `assessment_reports`，支持课程最新报告读取和报告生成 |
| 文件导出 | `export_jobs` + Redis/RQ 支持 Markdown/PDF/DOCX 学习档案和资源 PPTX 异步文件导出与下载 |
| 期末冲刺 | `exam_sprint` router 已接入，复用 `learning_paths` 和 `learning_tasks`，支持课程级冲刺计划生成和读取 |
| Docker | Compose 六服务可按默认端口启动，包含 PostgreSQL、Redis、backend、export-worker、frontend、nginx；backend 与 worker 共享导出卷 |
| 安全 | 用户数据隔离、Key 加密、脱敏返回和上传目录忽略已接入 |

当前后端已挂载的业务 router 是 `auth`、`dashboard`、`courses`、`materials`、`profiles`、`rag`、`settings`、`tutor`、`agents`、`resources`、`paths`、`practice`、`reports`、`exam_sprint` 和 `exports`。`demo` 仍只是前端 API 常量与后续接口设计，不属于当前已实现后端能力。

资源分层口径保持不变：`course_id != null` 是课程资源，`course_id == null` 预留个人全局资源。新资源使用 `content_json.schema_version=2` 和 `artifact.kind` 保存结构化产物，同时保留 Markdown fallback；旧资源不批量改写。`generation_mode` 区分模型增强与确定性来源，`review_mode` 区分 `model_and_rules` 和 `rules_only`，不能把规则 fallback 伪装成模型审核。资源、质量分和 trace 均不保存系统提示词、完整模型输入、密钥、完整资料或完整画像原文。

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
| 资源增强 | 六类 v2 资源、逐 Worker 模型增强、规则+模型审核、单次 Repair、交互渲染和 PPTX 队列已接入；资源版本编辑、个人全局资源仍未接入 |
| Agent 编排 hardening | 八条主链路已真接管；MaterialComparison、ExamSprint、ExportDossier 仍为后续专项 |
| 弱点复习增强 | Phase 14 已接入错题精确证据、诊断去重更新、已有路径重排；队列项编辑仍未接入 |
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
| Phase 8.2 | 已完成并增强 | 六 Worker 生成六类结构化学习资源，支持交互渲染和 PPTX |
| Phase 8.2.1 | 已完成并增强 | 确定性稿、逐 Worker 模型增强、真实审核、单次修订和结构化质量分 |
| Phase 9 | 已完成 | 课程级学习路径、规则掌握度图、弱点队列推荐资源和复习时间 |
| Phase 10 | 已完成 | 练习生成、确定性批改、弱点/掌握度反哺和学习报告展示第一刀 |
| Phase 11.1 | 已完成 | 期末冲刺模式第一刀，课程级 3/7/14 天冲刺计划 |
| Phase 11.2 | 已完成 | 资料对比第一刀，同课程多资料重点、考点、遗漏点和安全引用 |
| Phase 12.1 | 已完成 | Markdown 学习档案导出第一刀，同步返回课程级学习档案并在报告页下载 |
| Phase 12.2 | 已完成 | 交付基线、开源准备、MIT 许可证、验收证据和提交前文档初版 |
| Phase 13.1 | 已完成 | 学习产物 trace 字段、Graph 工作流口径和前端轻量轨迹入口 |
| Phase 13.2 | 已完成 | PDF/DOCX/PPTX 资料解析、主页联网/深思/语音、Markdown/PDF/DOCX 异步学习档案导出 |
| Phase 13 hardening | 已完成 | `HomeTutorGraph`、`CourseTutorGraph` 和 `ResourceGenerationGraph` 三条主链路真接管生产流程 |
| Phase 14 | 已完成 | `PathPlanningGraph`、`AssessmentGraph`、`ReportGraph` 真接管，错题证据与路径回流、报告趋势、pgvector SQL 课程检索和隔离 E2E |
| Phase 15 | 已完成 | `ProfileGraph`、`CourseBuilderGraph` 真接管，画像证据门控、v2 课程结构、adaptive 练习、草稿恢复和 React Flow/ECharts 可视化 |

## 下一步建议

当前可以继续推进 **Phase 15 后剩余流程接管与产品硬化**，重点是八条 Graph 的跨页面证据是否稳定、好懂、可恢复，同时逐步接管资料对比、冲刺和导出。

原因：

- Phase 7 已完成用户级画像、画像事件和课程问答候选证据闭环。
- Phase 8 已完成资源生成和可观测底座，Phase 9 已把课程级路径、掌握度、弱点推荐资源和复习时间接入。
- Phase 10 已把真实练习、答题结果、弱点队列、掌握度修正和学习报告接入最小闭环。
- Phase 11.1 已把课程资料、弱点、路径、练习、资源和报告建议沉淀为可展示的期末冲刺计划。
- Phase 11.2 已把课程资料之间的重复重点、疑似考点、独有点、遗漏点和安全引用接入资料库，不需要再造资料对比持久化表。
- Phase 12.1 已把课程报告、弱点、路径、资源和练习证据聚合为可下载的 Markdown 学习档案；Phase 13.2 已在此基础上补齐 `export_jobs` 和 Markdown/PDF/DOCX 异步导出。
- Phase 12.2 已把开源说明、开发指南、测试报告、用户指南、答辩问答、AI 辅助开发说明、MIT 许可证和验收证据索引补齐。
- Phase 14 已把路径、练习和报告推进为真实 LangGraph runner；客观数字保持规则控制，路径回流失败不会回滚练习，报告仍由用户主动生成。
- Phase 15 已把画像和资料建课推进为真实 LangGraph runner，并把画像证据、课程先修关系、adaptive 练习和可视化真正放进学习体验。

可选并行方向：

- 资料对比结果与期末冲刺的后续联动。
- 导出文件版式、剩余 Graph、课程空间移动体验和验收中发现问题的 P0/P1 修复。

后续继续保持代码、测试、工程文档和浏览器验收同步；不把 OCR、旧版 Office 或交付材料混入同一轮产品开发。
