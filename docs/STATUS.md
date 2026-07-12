# EduNova 当前状态

更新时间：2026-07-12

## 状态摘要

当前最新完成到 **Phase 18：AI 执行可靠性与质量评测**。

Phase 计划继续以 `docs/superpowers` 原始实施计划为准。Phase 13 已完成主页问答、课程问答和资源生成的真实 Graph 编排，Phase 14 已让路径、练习评估和报告进入真实 LangGraph，Phase 15 已让画像和资料建课进入生产 Graph，Phase 16 已让资料对比和期末冲刺进入生产 Graph，并打通冲刺来源练习的独立回流。

Phase 16 使用 Alembic `20260711_0013` 新增不可变 `material_comparison_runs`。`MaterialComparisonGraph` 从真实资料/课程分块生成规则底稿，模型只增强解释与排序；`ExamSprintGraph` 可显式消费对比版本，保留已完成进度并在冲刺来源练习后独立重排。普通练习不触发冲刺，重排失败不回滚评分、弱点或来源任务完成状态。

Phase 17 使用 Alembic `20260711_0014` 新增 `ai_jobs`。`CourseBuilderGraph` 和 `ResourceGenerationGraph` 继续保持原有同步接口兼容，同时通过 `edunova_ai` RQ 队列提供后台任务入口。任务状态由服务端持久化，Graph 节点通过独立 session 更新真实进度和心跳；取消在节点与持久化边界协作执行，失败或取消不保存半成品课程或资源。

Phase 18 使用 Alembic `20260711_0015` 新增隐私安全的 `model_call_runs`。十条 Graph、主页/课程流式问答和 Embedding 共用 `ModelExecutionRuntime`：只在当前配置内对瞬时故障有限重试，Redis 统一限制用户/全局并发并维护熔断状态；首 token 后的流中断不自动重放，也不持久化半截回答。离线 AI 质量回归集覆盖十条 Graph 的引用、敏感输出、结构和确定性数字边界，不依赖真实 API Key。

2026-07-12 已完成工作区背景融合与主页精简：资料库和资源工坊的工具栏、列表及内容区统一为一层连续工作画布，只保留必要分隔线，抽屉继续作为不透明浮层；主页删除预设快捷问题，“最近学习”改为按需打开完整课程抽屉，支持搜索、失败重试和课程跳转，不新增 `/app/courses` 列表路由。Docker 入口已用 `agent-browser` 验收 `1440px`、`1920px` 和 `390px`，三页及课程抽屉均无横向溢出，浏览器控制台无错误。

2026-07-12 已继续收口工作区色彩融合：主页背景改用低饱和青灰洗色和同色网格，资料库与资源工坊的连续画布、工具栏、表头和成果库统一为灰绿色阶；搜索、选择器、资源正文和不透明抽屉保留更高明度表面，避免整页染绿。Docker 入口已用 `agent-browser` 复验 `1440px`、`1920px` 和 `390px`，三页均无横向溢出，抽屉未透底，浏览器控制台无错误。

2026-07-12 已修复资源工坊右侧抽屉被宽屏工作台包含块限制的问题：`StudioDrawer` 现在与 `PageFrame` 同级渲染，遮罩和抽屉以浏览器视口为边界，不再被成果画布外框裁切；资料库与主页抽屉继续保持视口级浮层结构。

2026-07-12 已将应用视觉固定为当前浅色青灰主题：侧栏不增加额外外观按钮，前端不保存主题偏好，也不维护第二套组件色彩分支，把视觉维护集中在学生学习主流程。

2026-07-11 已完成课程空间桌面工作区重做：默认首屏只突出课程、问答和固定输入；每条持久化回答独立绑定自己的引用、trace 和历史问题；A3 八步状态、弱点操作和建课轨迹进入覆盖式学习进度抽屉；原学习模式改为课程内容，按章节展示知识点、概览和 React Flow 图谱，AI 辅导使用覆盖抽屉。该轮不改后端、数据库或路由。

2026-07-11 已收口课程空间学习进度同步：课程栏和抽屉百分比统一为当前课程知识点 `score` 平均值；学习状态、掌握度、资源、当前路径和最新报告共用课程闭环 Query Key。相关业务操作完成后主动失效缓存，打开抽屉会强制同步五组数据；部分失败保留最后成功内容并允许重试。A3 八步继续表达离散步骤状态，不与掌握度混用。

2026-07-11 已完成资源工坊桌面成果工作台重做：`/app/studio` 使用纵向成果库、中央资源画布和统一右侧覆盖抽屉；搜索、六类筛选、`resource_id` URL 恢复、质量/引用/真实 Graph 轨迹均绑定当前成果。异步生成继续支持刷新恢复、取消和重试，完成后自动选中新成果；旧 `StudioDock`、状态示例区和多轮叠加样式已删除。该轮不改后端、数据库、资源协议或移动端产品范围。

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
- 课程空间已经改为课程对话工作区：默认问答、逐回答证据与行动、按需课程内容、学习进度抽屉；登录后首页 `/app` 继续保持轻量入口，不改成驾驶舱。
- 学习画像已由 `ProfileGraph` 接管，画像页展示逐维可信度、候选/已应用证据和真实轨迹。
- Phase 7.2 已明确用户级画像和课程级学习状态的边界：用户级画像只有一份，课程级目标、薄弱点、掌握度、复习队列和学习路径按课程聚合。
- Phase 7.3 已把课程问答弱点候选事件同步为课程级 `weakness_review_queue` 待确认复习项，并在课程空间展示真实“待复习弱点”摘要。
- Phase 7.4 已为课程级弱点复习项补齐确认、开始、完成和软忽略状态流转，课程空间可以直接操作真实队列项。
- 2026-07-11 Phase 16 后，`ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph`、`MaterialComparisonGraph` 和 `ExamSprintGraph` 已真接管十条生产主链路；学习档案导出继续使用确定性 Service + Redis/RQ Worker。
- `/resources` 可基于当前用户课程生成讲解、思维导图、练习、代码实操、PPT 和动画图解。六个 Worker 分别执行模型增强并保留确定性 fallback，ReviewAgent 结合结构规则和模型审核，失败资源最多修订一次；旧 Markdown 资源继续兼容读取。
- Phase 9 已挂载 `/paths`，可为当前用户课程生成 active 学习路径、更新任务状态；`/app/path` 现已升级为“个性化路径 / 期末冲刺”双模式宽屏任务工作台，生成、掌握度、依据和轨迹按需进入右侧抽屉。
- Phase 9 已实现 `/courses/{course_id}/mastery-map`，并让 `/courses/{course_id}/learning-state` 返回真实路径摘要、掌握度摘要、弱点推荐资源和下次复习时间。
- Phase 14 已将 `/practice` 和 `/reports` 升级为真实 Graph：练习创建/提交保留确定性分数并生成错因诊断，错题与弱点证据精确绑定，已有路径自动重排；报告聚合最近 5 次练习并展示规则趋势、证据摘要和真实轨迹。
- Phase 16 已用 `ExamSprintGraph` 接管 `/exam-sprint`，可基于课程证据、显式资料对比、画像、弱点、练习、资源和报告生成 3/7/14 天冲刺计划，并在冲刺来源练习后保留进度重排剩余任务。
- Phase 11.2 已挂载 `/materials/compare`，可对同一课程下 2 份以上已绑定资料做确定性对比，输出重复重点、疑似考点、单资料独有点、试题独有点、遗漏复习点、优先复习顺序和安全引用，并在 `/app/library` 展示。
- Phase 12.1 已挂载 `/exports/learning-dossier`，可同步导出当前用户课程级 Markdown 学习档案；Phase 13.2 已挂载 `/exports/learning-dossier/jobs`、`/exports/{job_id}` 和 `/exports/{job_id}/download`，可通过 Redis/RQ worker 异步生成 Markdown/PDF/DOCX 学习档案，并在 `/app/reports` 选择格式下载。
- Phase 12.2 已补齐交付基线文档、开源说明、MIT 许可证、用户指南、答辩问答、测试报告和验收证据索引。

2026-07-11 后，十条主链路已经由真实 Graph runner 编排并落 `agent_run_logs`：动态画像、智能建课、主页问答、课程问答、资源生成、学习路径、练习评估、学习报告、资料对比和期末冲刺。学习档案导出、认证、设置、Dashboard 等能力保持普通服务。

当前仍然不是完整商业产品。课程级路径、错题诊断与回流、掌握度、学习报告、资料对比版本、期末冲刺联动、资料解析、学习档案导出和隔离 Docker E2E 已接入；OCR、旧版 Office、扫描件解析和更广的端到端异常恢复仍在后续阶段。

## 已完成主链路

| 范围 | 当前能力 | 关键入口 |
| --- | --- | --- |
| 认证 | 注册、登录、读取当前用户、退出、受保护路由 | `/api/v1/auth/*` |
| 首页总览 | 当前用户课程、资料、主页历史和空状态 | `/api/v1/dashboard/summary` |
| 主页会话 | `HomeTutorGraph`、资料级 RAG、联网/深度规划、SSE Markdown、Review/Repair、连续追问、历史切换、改名、软删除和刷新保留 | `/api/v1/tutor/sessions` |
| 资料库 | 上传、列表、详情、解析进度、课程关联、不可变资料对比版本和最近结果恢复 | `/api/v1/materials/*` |
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
| 期末冲刺 | `ExamSprintGraph` 生成/恢复 3/7/14 天计划，支持对比证据、针对性练习和独立重排 | `/api/v1/exam-sprint/*` |
| 资料对比 | `MaterialComparisonGraph` 生成同课程资料安全对比、不可变版本和真实 trace | `/api/v1/materials/compare`、`/api/v1/materials/comparisons/*` |
| 交付基线 | 开源说明、开发指南、测试报告、用户指南、答辩问答、MIT 许可证和验收证据索引 | `docs/*`、`LICENSE` |

## 当前前端状态

| 页面 | 当前状态 |
| --- | --- |
| `/login` | 调用真实登录接口，不提供共享演示学生按钮 |
| `/register` | 调用真实注册接口，可选择空白开始或复制人工智能导论 |
| `/app` | GPT 式主页，问候使用真实昵称，不展示预设快捷问题；主页资料浮层读取完整资料库，并可恢复资料库传入的选料状态；最近学习可按需打开完整课程抽屉；活动对话继续流式消费 `HomeTutorGraph`，支持资料级 RAG、联网、深度规划、语音、朗读和历史管理 |
| `/app/library` | 连续画布式宽屏资料工作台；全宽文件表格、URL 详情恢复、安全章节摘要、关联课程、主页选料入口、多选资料对比抽屉、Graph 轨迹和显式冲刺入口 |
| `/app/courses/:courseId` | 桌面课程对话工作区；固定课程栏与输入、逐回答来源/trace/行动、学习进度抽屉、课程内容与 React Flow 图谱 |
| `/app/settings` | 管理多套模型配置，支持 Provider 预设、保存、测试、设默认和删除 |
| `/app/studio` | 连续画布式桌面成果工作台；左侧成果库、中央六类资源画布、生成/详情覆盖抽屉、URL 成果恢复和 PPTX 导出 |
| `/app/profile` | 读取真实 8 维画像、逐维可信度、候选/已应用证据和 ProfileGraph 轨迹 |
| `/app/practice` | 支持 adaptive 难度、最近练习/草稿恢复、确定性评分、诊断和路径回流 |
| `/app/reports` | 读取真实课程和最新报告，可生成学习报告；展示真实分数、掌握度更新、薄弱点、证据摘要和下一步建议；可创建异步导出任务并下载 Markdown/PDF/DOCX 学习档案 |
| `/app/path` | 读取普通路径、掌握度图和当前冲刺计划；显式消费 `comparison_id` 并进入指定必刷题练习 |

当前前端不再使用中间横向的 `ActionNotice` 提示。历史切换、筛选、开关和详情展开依靠选中态或内容变化表达；上传失败、发送失败、课程生成失败和表单校验错误使用局部提示；模型配置保存、测试、设默认和删除使用右下角轻量 toast。

独立 `DemoEntryPage`、`TutorPage` 及其前端假接口已删除。快速体验使用注册页的示例课程选项；AI 辅导直接在课程空间完成。`/demo` 进入 404，旧 `/app/tutor` 仅保留受保护兼容跳转并回到 `/app`。

主页输入区的资料状态只显示已选资料数量，并贴近底部输入框；联网搜索和深度思考会进入发送 payload，回答下方展示真实返回来源和 `home_tutor` trace。未配置搜索 Key 时只显示 warning，不伪造网页来源。

普通二级路由（资料库、资源工坊、画像、设置、路径、练习和报告等）复用左侧主页工作区侧栏，并读取 `/dashboard/summary` 的真实主页历史；从这些页面点击主页历史会回到 `/app` 并打开对应会话。课程空间仍显示当前课程内历史，不混入主页历史。

Phase 13 前端视觉硬化后，桌面端继续保留 264px / 68px 的展开与收起侧栏；`900px` 及以下视口默认收起为 58px 顶部导航条，点击后以覆盖式抽屉显示完整导航、历史和账号入口。移动端导航动作完成后自动收起抽屉。`/app`、普通 `PageFrame` 路由和课程空间复用同一响应式状态逻辑；键盘焦点统一使用可见青绿色焦点环，composer 使用 `:focus-within` 显示输入焦点。

课程空间采用“默认问答 + 按需课程内容”。目标、依据、下一步、A3 八步状态和弱点队列位于学习进度抽屉；课程栏与抽屉显示同一知识掌握度平均值。打开抽屉会同步学习状态、掌握度、资源、路径和报告，部分失败保留最后成功内容。真实引用、六类结构化资源、路径、练习、报告和协作轨迹绑定到各自 Assistant 回答并就地展开。资源工坊继续作为成果库，轨迹只展示安全摘要，不展示原始思维链。

## 当前后端状态

| 模块 | 当前状态 |
| --- | --- |
| FastAPI 应用 | 已有 `/api/health` 和 `/api/v1` 路由结构 |
| 数据库 | PostgreSQL + pgvector，Alembic 迁移到当前 head |
| 课程包 | 人工智能导论内置课程包可幂等导入 |
| 认证 | bcrypt、JWT、`starter_mode` 和当前用户依赖已接入 |
| 资料库 | `materials`、`material_chunks`、`course_material_links` 与 `material_comparison_runs` 已接入；PDF/DOCX/PPTX 可解析，图片/扫描件不做 OCR；资料对比由真实 Graph 生成并版本化 |
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
| 期末冲刺 | `ExamSprintGraph` 复用 `learning_paths` 和 `learning_tasks`，支持当前计划恢复、对比证据和冲刺来源练习回流 |
| Docker | Compose 七服务可按默认端口启动，包含 PostgreSQL、Redis、backend、export-worker、ai-worker、frontend、nginx；AI 与文件导出使用独立 RQ 队列 |
| 安全 | 用户数据隔离、Key 加密、脱敏返回和上传目录忽略已接入 |

当前后端已挂载的业务 router 是 `auth`、`dashboard`、`courses`、`materials`、`profiles`、`rag`、`settings`、`tutor`、`agents`、`ai_jobs`、`resources`、`paths`、`practice`、`reports`、`exam_sprint` 和 `exports`。`demo` 仍只是前端 API 常量与后续接口设计，不属于当前已实现后端能力。

资源分层口径保持不变：`course_id != null` 是课程资源，`course_id == null` 预留个人全局资源。新资源使用 `content_json.schema_version=2` 和 `artifact.kind` 保存结构化产物，同时保留 Markdown fallback；旧资源不批量改写。`generation_mode` 区分模型增强与确定性来源，`review_mode` 区分 `model_and_rules` 和 `rules_only`，不能把规则 fallback 伪装成模型审核。资源、质量分和 trace 均不保存系统提示词、完整模型输入、密钥、完整资料或完整画像原文。

课程问答在 Phase 7.1 后会把明确困惑/薄弱信号沉淀为画像候选事件，但只保存课程、会话、消息、`trace_id` 和引用摘要，不保存完整用户问题、系统提示词、模型输入或资料原文。Phase 7.3 的 `/courses/{course_id}/learning-state` 会把当前课程的这些候选事件按知识点或安全标题同步为 `pending` 待确认复习项，不把候选事件直接宣称为已诊断弱点。Phase 7.4 后，学生可以把队列项确认为 `confirmed`、开始为 `reviewing`、完成为 `completed`，也可以软忽略为 `dismissed`；`dismissed` 不在主列表展示，但继续参与去重。

Phase 7.2 的分层口径：

- `student_profiles` 保存用户级长期画像，只保留一份。
- `profile_events` 保存证据流，可带课程来源信息。
- `weakness_review_queue` 保存课程级可执行复习项，Phase 7.3 已接入课程问答候选事件到 `pending` 项的同步，Phase 7.4 已接入确认、开始、完成和软忽略状态流转，必须绑定 `course_id`。
- `learning_paths` 和 `learning_tasks` 保存 Phase 9 生成的课程级 active 路径和任务，旧 active 路径会归档为 `archived`。
- Phase 11.1 期末冲刺同样复用 `learning_paths` 和 `learning_tasks`，但使用 `sprint_active` / `sprint_archived` 和 `plan_json.kind="exam_sprint"`，不会影响普通 `active` 学习路径。
- `/courses/{course_id}/learning-state` 是课程级学习状态聚合接口，不新增通用 `learning_events` 表；Phase 9 后同时返回路径摘要、掌握度摘要、推荐资源和复习时间，Phase 10 后练习结果会反哺掌握度和 `practice_assessment` 来源弱点。

课程空间和普通二级路由已经去掉前端 demo 数据兜底：真实课程加载中不会显示“人工智能导论”示例课程，资源工坊初始不展示假成果或组件状态示例，报告页不展示固定资料证据，普通二级路由侧栏不再注入主页 demo 历史，而是复用真实主页历史并回到 `/app` 打开会话。

## 尚未完成

| 能力 | 当前处理 |
| --- | --- |
| OCR 和图片题目识别 | 图片只入库，不做识别；扫描件 PDF 不伪装 OCR |
| 旧版 Office 解析 | `.doc`、`.ppt` 只入库，不做深度解析 |
| 讯飞原生 Embeddingp/Embeddingq | 暂不接入，当前用 OpenAI-compatible embeddings 或本地 fallback |
| 资料对比增强 | Phase 16 已完成安全结果持久化、最近版本恢复、真实 Graph 轨迹和期末冲刺联动；不提供完整原文对照页 |
| 资源增强 | 六类 v2 资源、逐 Worker 模型增强、规则+模型审核、单次 Repair、交互渲染和 PPTX 队列已接入；资源版本编辑、个人全局资源仍未接入 |
| Agent 编排 hardening | 十条学习主链路已真接管；学习档案导出明确保持普通 Service + RQ Worker |
| 弱点复习增强 | Phase 14 已接入错题精确证据、诊断去重更新、已有路径重排；队列项编辑仍未接入 |
| 学习路径 | Phase 9 已接入真实路径生成、当前路径读取、任务状态更新和课程页摘要 |
| 掌握度图 | Phase 10 已接入练习评估修正；仍是规则计算，不单独持久化 |
| 学习报告导出 | Phase 13.2 已接入 Markdown/PDF/DOCX 异步导出；后续可继续打磨版式和下载体验 |

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
| Phase 16 | 已完成 | `MaterialComparisonGraph`、`ExamSprintGraph` 真接管，不可变对比版本、显式冲刺证据和来源练习独立重排 |
| Phase 17 | 已完成 | `AIJobRuntime`、`ai_jobs`、独立 AI Worker、建课/资源后台任务、节点进度、恢复、取消、重试和全局任务托盘 |
| Phase 18 | 已完成 | `ModelExecutionRuntime`、同配置重试、Redis 并发/熔断、模型调用安全审计、Trace 聚合和十 Graph 离线质量评测 |

## 下一步建议

Phase 18 已完成十条 Graph 共用的模型执行可靠性底座。后续应优先根据 Docker、真实模型评测和移动端验收发现的问题继续产品打磨；OCR、旧版 Office 和扫描件仍作为独立范围，不与可靠性底座混写。

原因：

- Phase 7 已完成用户级画像、画像事件和课程问答候选证据闭环。
- Phase 8 已完成资源生成和可观测底座，Phase 9 已把课程级路径、掌握度、弱点推荐资源和复习时间接入。
- Phase 10 已把真实练习、答题结果、弱点队列、掌握度修正和学习报告接入最小闭环。
- Phase 11.1 已把课程资料、弱点、路径、练习、资源和报告建议沉淀为可展示的期末冲刺计划。
- Phase 16 已把课程资料对比升级为不可变版本，并通过显式 `comparison_id` 接入期末冲刺。
- Phase 12.1 已把课程报告、弱点、路径、资源和练习证据聚合为可下载的 Markdown 学习档案；Phase 13.2 已在此基础上补齐 `export_jobs` 和 Markdown/PDF/DOCX 异步导出。
- Phase 12.2 已把开源说明、开发指南、测试报告、用户指南、答辩问答、AI 辅助开发说明、MIT 许可证和验收证据索引补齐。
- Phase 14 已把路径、练习和报告推进为真实 LangGraph runner；客观数字保持规则控制，路径回流失败不会回滚练习，报告仍由用户主动生成。
- Phase 15 已把画像和资料建课推进为真实 LangGraph runner，并把画像证据、课程先修关系、adaptive 练习和可视化真正放进学习体验。

可选并行方向：

- 继续扩展十条 Graph 的隔离 E2E、异常恢复和移动端验收。
- 导出文件版式、剩余 Graph、课程空间移动体验和验收中发现问题的 P0/P1 修复。

后续继续保持代码、测试、工程文档和浏览器验收同步；不把 OCR、旧版 Office 或交付材料混入同一轮产品开发。
