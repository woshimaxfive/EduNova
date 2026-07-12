# EduNova 架构设计说明

日期：2026-07-01

## 1. 架构目标

EduNova 的架构目标是支持一个可演示、可部署、可开源、可扩展的 AI 个性化学习空间。第一版重点不是堆功能，而是保证学生学习主链路稳定、AI 输出可解释、多智能体过程可追踪、上传资料能形成课程知识库。

核心原则：

1. 学生端优先，避免第一版变成泛教务平台。
2. 业务服务和 AI 编排解耦，避免所有逻辑堆在接口层。
3. 大模型 Provider 可替换，避免绑定单一厂商。
4. RAG、引用、ReviewAgent 贯穿 AI 输出，降低幻觉风险。
5. 长任务可追踪，前端不长时间白屏。
6. 数据按用户和课程隔离，便于后续开源多人使用。
7. Docker Compose 一键部署，便于比赛提交和同学试用。

## 2. 总体架构

```text
React + TypeScript 学生 AI 学习空间
        ↓ HTTP / SSE
FastAPI 后端 API
        ↓
业务服务层
        ↓
LangGraph 多智能体编排
        ↓
模型 Provider + RAG 检索 + PostgreSQL + Redis + 文件存储
```

部署视角：

```text
浏览器
  ↓
Nginx
  ├── 前端静态资源
  └── /api 转发到 FastAPI
          ├── PostgreSQL + pgvector
          ├── Redis
          ├── 本地文件存储
          └── 外部大模型服务
```

## 3. 前端架构

前端使用 React + TypeScript + Vite，定位为学生 AI 学习空间。具体设计基线见 [UI_UX_DESIGN.md](UI_UX_DESIGN.md)，入口与路由设计见 [FRONTEND_ROUTING_DESIGN.md](FRONTEND_ROUTING_DESIGN.md)，课程空间双模式改造见 [COURSE_SPACE_DESIGN.md](COURSE_SPACE_DESIGN.md)。

第一版前端不采用后台管理式左侧菜单，也不把首屏做成卡片堆。

当前应用区统一使用 `AppSidebar` 贴边工作区外壳：

- 主页 `/app` 显示主页历史。
- 课程空间显示当前课程的课程内历史。
- 普通二级路由不注入 demo 历史。
- 个人资料、设置和退出登录固定在侧栏底部。
- “新建对话”回到 `/app` 主页。

主页 `/app` 是总 AI 学习入口：

- 初始态展示中心输入框和最近学习。
- 发送后进入对话态，输入区固定到下方。
- 输入区支持上传、资料库、生成课程、搜索、思考、语音。
- Enter 发送，Shift+Enter 换行。

资料库 `/app/library` 是文件库式资料管理页：

- 资料独立存在，不默认归属课程。
- 支持文档/图片筛选、搜索、详情和上传。
- 从资料生成课程使用上层浮层，不替换当前页面。

课程空间 `/app/courses/:courseId` 承载课程上下文：

- 真实课程标题、资料数、知识点数和知识点列表。
- 课程内历史、课程消息和引用持久化。
- 课程知识库检索、引用来源、证据层和流式回答。
- 资源、路径、练习和报告入口仍保留为后续学习闭环承载位。
- Phase 6.5 前端采用双模式：默认问答模式承载课程版 AI 对话，知识点入口和来源进入学习模式，中间显示学习内容，右侧提供上下文 AI 辅导。

当前已经接入真实后端的数据：

- 注册登录和 `starter_mode` 初始化。
- 主页 summary、主页历史和资料库浮层。
- 个人资料库上传、列表、详情和进度。
- TXT/Markdown/PDF/DOCX/PPTX 已解析资料生成课程。
- 课程详情、知识点、课程会话、RAG 引用和流式回答。
- 多模型配置管理、默认配置和连接测试。
- 主页已选资料、联网搜索、深度回答指令、`home_tutor` trace、浏览器语音输入和朗读。
- 资源工坊、画像、路径、练习、报告、期末冲刺、资料对比和学习档案导出。

当前仍需继续打磨的区域：

- Graph trace 视觉表达和更多浏览器 E2E。
- OCR、旧版 Office 和扫描件解析。
- 资料对比结果持久化、显式带入期末冲刺，以及冲刺来源练习完成后的独立计划重排。
- 导出文件版式细节。

深度思考和联网搜索只属于对话输入区的运行期工具，不属于模型连接设置。

目录规划：

```text
frontend/src/
├── api/              接口调用
├── app/              路由和应用入口
├── components/       通用组件
├── features/         按业务能力拆分的功能模块
├── pages/            页面
├── styles/           全局样式和设计 token
├── types/            类型定义
└── visualizations/   学习画布、图谱、雷达图和思维导图
```

首页首屏结构：

```text
贴左边缘主页侧栏：主页历史对话、新建对话、资料库、资源工坊、个人资料、设置、退出登录，可收起
中央：轻量输入框，支持文件上传、选择资料、生成课程
发送后：主页对话流 + 下方固定输入区
输入区：上传资料文件 / 打开资料库 / 生成课程 / 联网搜索激活态 / 深度思考激活态 / 语音 / Enter 发送
下方：最近学习轻量列表 / 最近课程入口
回答下方：引用来源、学习路径建议、Agent 过程，可展开
```

核心前端模块：

| 模块 | 作用 |
| --- | --- |
| `AppSidebar` | 受保护应用区统一贴边工作区侧栏，普通二级路由承载资料库、资源工坊、个人资料、设置、退出登录和收起控制；主页承载主页历史，课程空间承载课程内历史 |
| `HomeChat` | 总 AI 学习主页，对话可以独立存在，也可以移入某一课程 |
| `CommandBar` | 自然语言主入口，触发上传资料、选择资料、生成课程、基于资料问答和保存回答 |
| `MaterialContextPanel` | 轻量资料上下文，连接独立资料库、主页对话和课程资料 |
| `LearningCanvas` | 课程内可视化模块，展示课程焦点、知识点网络、学习路径节点、资料流入和薄弱点 |
| `SourceCluster` | 课程内展示资料源、解析状态和引用覆盖度 |
| `StudioDock` | 展示讲解、练习、思维导图、代码实操、PPT、动画图解六类结构化产物 |
| `EvidenceLayer` | 展示引用来源、Agent 轨迹、ReviewAgent 结果、低依据提示和质量评分 |
| `AgentTimeline` | 展示多智能体步骤、耗时、状态和失败节点 |
| `MasteryVisual` | 展示画像雷达、知识点掌握状态和薄弱点复习队列 |

主要页面：

| 页面 | 作用 |
| --- | --- |
| 登录/注册 | 进入系统 |
| 学习主页 | 第一屏主体验，承载贴边可收起主页历史、侧栏账号入口、轻量输入框、发送后主页对话态、资料选择、文件上传和最近课程 |
| 资料库 | 文件库式独立资料管理，支持真实上传、搜索、文档/图片筛选、查看详情反馈、作为主页参考和从已解析资料生成真实课程；生成课程以浮层覆盖当前页面 |
| 课程空间 | 默认问答模式 + 按需学习模式，承载课程内历史对话、真实引用、混合检索状态、知识点/引用学习内容、AI 辅导、练习和报告等学习闭环入口 |
| 学习路径 | 独立路径工作区，展示阶段任务、路径依据和下一步行动，后续接 `learning_paths` 与 `learning_tasks` |
| 资源工坊 | 查看和管理生成的学习资源；当前已补资源生成工作台、生成队列和输出区 |
| 画像 | 查看学习目标、基础、节奏、薄弱点和画像证据 |
| AI 辅导 | 课程空间内的流式问答、引用与连续追问能力，不单设中转页面 |
| 练习 | 作答、批改反馈和薄弱点复习队列 |
| 报告 | 查看画像、掌握度、薄弱点、学习报告和导出入口 |
| 设置 | 配置模型 Provider、个人信息、隐私数据边界和导出数据 |

路由结构：

| 路由组 | 路径 |
| --- | --- |
| 公开入口 | `/`、`/login`、`/register` |
| 应用区 | `/app`、`/app/library`、`/app/path`、`/app/courses/:courseId`、`/app/studio`、`/app/profile`、`/app/practice`、`/app/reports`、`/app/settings` |
| 兼容跳转 | 旧 `/app/tutor` 地址经登录保护后回到 `/app`；不再对应独立页面 |
| 兜底 | `*` |

路由保护：

- `ProtectedRoute` 统一保护 `/app/*`。
- `PublicOnlyRoute` 处理已登录用户访问 `/login` 和 `/register`。
- API client 收到 401 后清理登录态并跳回 `/login`。
- 快速体验通过真实注册流程复制示例课程，不创建共享账号或前端假 session。

前端状态分工：

- 登录态：Zustand 保存 token 和用户信息。
- 服务端数据：React Query 管理请求、缓存和刷新。
- 页面临时状态：React 本地状态。
- 长任务进度：轮询或 SSE。

前端技术选型：

| 能力 | 选型 |
| --- | --- |
| 样式 | Tailwind CSS + 自定义设计 token |
| 无障碍基础组件 | Radix UI 或 shadcn/ui 按需引入 |
| 动效 | Motion，所有动效支持 reduced motion |
| 学习画布 | React Flow 或自定义 SVG/Canvas |
| 数据可视化 | ECharts |
| Markdown/思维导图 | Markdown 渲染 + Mermaid / Markmap（npm 包使用 `markmap-lib` 和 `markmap-view`） |

当前已落地的前端基础模块：

| 模块 | 当前状态 |
| --- | --- |
| `frontend/package.json` | pnpm、Vite、TypeScript、React、Tailwind CSS v4、Vitest、ESLint 依赖和脚本 |
| `frontend/src/app` | `App`、`AppProviders`、集中路由、路由常量、`ProtectedRoute`、`PublicOnlyRoute` |
| `frontend/src/features/auth/authStore.ts` | Zustand 登录态，保存真实 JWT token 和当前用户信息 |
| `frontend/src/features/auth/authMappers.ts` | 把后端 `display_name`、`starter_mode` 映射成前端 `displayName`、`starterMode` |
| `frontend/src/api/client.ts` | Axios 客户端，默认基础路径 `/api/v1`，自动附加 token，401 清理登录态并返回登录页 |
| `frontend/src/api/*.ts` | 按业务域拆分的前端 API 合同模块，默认基础路径 `/api/v1` |
| `frontend/src/features/workspace/workflowState.ts` | 上传建课生命周期和短状态信号的纯状态模型 |
| `frontend/src/pages` | 登录、注册、学习空间、资料库、课程空间、学习路径、资源工坊、画像、练习、报告、设置和 404；AI 辅导由课程空间直接承载 |
| `frontend/src/components` | 贴边侧栏、学习空间壳子、学习画布、资料源簇、命令栏、资源输出区、证据层、Agent 轨迹、局部反馈和轻量 toast |
| `frontend/src/styles/global.css` | 视觉 token、响应式布局、reduced motion 和 reduced transparency 基础 |

前端 API 模块当前分工：

- `auth.ts`：注册、登录、读取当前用户、退出。
- `dashboard.ts`：学习空间首页 summary。
- `materials.ts`：上传、列表、详情、进度和课程关联。
- `courses.ts`：课程列表、详情、v2 概览、知识点先修关系和智能建课。
- `rag.ts`：课程知识库检索和混合检索字段。
- `tutor.ts`：主页/课程会话、消息、引用、主页联网/深思/资料参数，以及 home/course 共用 SSE 的状态、来源、token、Review 替换和完成事件。
- `exports.ts`：旧同步 Markdown 学习档案导出和 Markdown/PDF/DOCX 异步导出任务。
- `settings.ts`：模型配置读取、保存、测试、多配置管理和默认配置。

当前边界：

- Phase 4.1 已完成真实注册、登录、读取当前用户和退出闭环；注册 starter mode 已落入后端注册接口和用户初始化流程。
- Phase 4.2 已完成受保护的 `/dashboard/summary` 首页总览；当前 `/app` 左侧主页历史、最近课程、主页资料库浮层资料和 blank/ai_intro 空状态来自当前登录用户的真实 summary，不再使用前端假课程、假资料和假历史伪装真实数据。
- Phase 4.3 已完成受保护的 `/tutor/sessions` 主页会话与消息持久化；当前 `/app` 首次发送会创建 home session，连续追问复用当前 session，主页 assistant 调用当前用户默认模型生成普通回答，点击左侧历史会从后端读取真实 messages，刷新后历史由 `/dashboard/summary` 保留。
- Phase 4.4 已完成受保护的 `/materials` 真实资料库闭环；当前 `/app` 上传资料会写入个人资料库并刷新 `/dashboard/summary`，`/app/library` 从 `/materials` 读取当前用户资料，支持文档/图片筛选、搜索、详情反馈和上传刷新。
- Phase 13.2 已完成 PDF/DOCX/PPTX 文本解析；当前 `/app` 和 `/app/library` 可用已解析 TXT/Markdown/PDF/DOCX/PPTX 资料生成课程，并跳转 `/app/courses/:courseId`。旧版 DOC/PPT、图片和扫描件不伪装解析完成。
- Phase 5.2 已完成受保护的 `/rag/search` 课程知识库检索；Phase 6.4 后检索会优先融合关键词分数和向量分数，并把真实资料、章节、切片引用和检索状态保存到 assistant 消息。
- Phase 5.3 已完成课程空间 `scope=course` 会话持久化；课程侧栏历史来自 `/tutor/sessions?scope=course&course_id=...`，点击历史会恢复真实 messages 和 `citation_json`。
- 当前主页 assistant 由 `HomeTutorGraph` 接管并使用流式输出。主页允许模型通用知识，已选资料通过独立 `material_chunks` 做资料级混合检索，联网结果作为可追溯证据；未配置搜索 Key 时 warning 只进入来源/轨迹区，不伪造网页来源。课程空间继续使用严格课程 RAG，两者不混用证据边界。
- 当前 `/app/courses/:courseId` 的课程标题、知识点、课程历史、课程消息和课程引用来自真实接口。
- 命中引用且模型可用时，课程 assistant 内容来自 OpenAI-compatible 模型回答。
- 课程页优先使用 `fetch` + `ReadableStream` 消费 SSE。
- Phase 6.4 起课程引用来自混合检索，缺少外部 embedding 配置时显式显示本地 fallback。
- Phase 6.5 起课程页默认不再常驻知识画布、资源区、证据层、横向知识点条或主区重复历史；来源、生成资源、学习路径和课堂协作轨迹收敛到回答下方，知识点入口和引用可进入学习模式。
- 资源、学习路径和 Agent 轨迹已经接入真实接口；后续重点是体验和验收打磨。
- 当前资料库、资源工坊、画像、课程空间辅导、练习、报告和设置均不依赖核心样例数据兜底；只保留真实空态和错误态。
- 当前前端已移除 `ActionNotice` 类全局横向提示条；按钮反馈优先通过选中态、列表刷新、详情面板、输入内容和真实路由跳转表达。失败、校验错误和模型不可用等需要用户处理的状态使用局部 `InlineFeedback`，模型配置保存、设默认、删除和连接测试等短确认使用右下角 toast；后续接 API 时应把对应 handler 替换为 React Query mutation、轮询或 SSE 任务状态。
- 上传解析状态由 `/materials/{material_id}/progress` 驱动；智能建课状态由 `/courses/from-materials/jobs` 和 `/ai-jobs/*` 的持久化节点进度驱动，不使用前端伪进度。
- Markmap 已用于结构化思维导图，Mermaid 已用于动画图解；React Flow 已接管课程学习模式的知识点与先修关系图，ECharts 已用于路径掌握度和报告练习趋势。旧 CSS 绝对定位知识画布已删除。

## 4. 后端架构

后端使用 FastAPI，采用分层结构。

```text
backend/app/
├── api/          HTTP 接口层
├── core/         配置、安全、日志、SSE
├── db/           SQLAlchemy Base、engine、Session
├── models/       SQLAlchemy 数据模型
├── schemas/      Pydantic 请求响应模型
├── services/     业务服务
├── agents/       多智能体编排
├── providers/    大模型适配
├── rag/          向量检索和引用
└── tasks/        长任务和进度
```

当前已落地的后端基础模块：

| 模块 | 当前状态 |
| --- | --- |
| `backend/app/main.py` | FastAPI 应用和 `/api/health` |
| `backend/app/core/config.py` | 环境配置，读取数据库、Redis、JWT、上传资料、联网搜索、导出队列、AI 任务队列和模型 Provider 配置 |
| `backend/app/db/base.py` | SQLAlchemy Declarative Base |
| `backend/app/db/session.py` | 数据库 engine、Session 工厂和依赖入口 |
| `backend/app/models` | 用户、课程、资料、知识点、知识切片核心模型，以及画像、路径、资源、Agent 轨迹、练习、报告、对话和模型设置基础模型 |
| `backend/app/data/builtin_courses` | 内置课程包数据 |
| `backend/app/services/course_seed.py` | 内置课程导入服务 |
| `backend/app/services/tutor.py` | 主页/课程会话 API 边界和依赖装配；`HomeTutorGraphRunner` 接管主页上下文、路由、资料检索、联网、规划、回答、Review/Repair 和持久化，`CourseTutorGraphRunner` 接管严格课程 RAG 问答 |
| `backend/app/services/model_settings.py` | 模型设置服务，负责用户多模型配置、系统兜底配置解析、Fernet 加密保存用户 Key、脱敏摘要、连接测试、默认配置切换、聊天模型和 embedding 模型运行时配置优先级 |
| `backend/app/services/model_execution.py` | 统一模型执行运行时，负责同配置有限重试、Redis 并发租约、熔断、取消检查和独立安全审计 |
| `backend/app/services/embeddings.py` | Embedding 服务，负责 OpenAI-compatible `/embeddings` 调用编排、本地 `local-hash-1536` fallback、知识切片向量写入和 metadata 标记 |
| `backend/app/services/course_answers.py` | 回答服务，负责主页学习 prompt、资料/网页来源摘要、深度回答指令、课程引用受控 prompt、非流式或流式模型 Provider 调用、未配置和模型失败处理 |
| `backend/app/services/material_parsers.py` | 资料解析器，负责 TXT/Markdown/PDF/DOCX/PPTX 文本抽取，并明确 OCR、旧版 Office 和扫描件边界 |
| `backend/app/services/materials.py` | 个人资料库服务，负责上传保存、解析、列表、详情、进度和课程资料关联 |
| `backend/app/services/material_retrieval.py` | 共享资料分块和主页资料级 RAG，负责上传后切片、既有资料惰性补齐、当前用户选中资料限制、关键词/pgvector 混合排序和安全引用 |
| `backend/app/services/web_search.py` | Tavily-compatible 联网搜索服务，未配置 Key 时返回 warning，不生成假来源 |
| `backend/app/services/courses.py` | 课程 API 边界和依赖装配；`CourseBuilderGraphRunner` 接管来源大纲、课程结构、知识点、切片、embedding、审核/修订与事务持久化 |
| `backend/app/services/exports.py` | 学习档案导出服务，负责旧同步 Markdown 兼容接口和 Markdown/PDF/DOCX 异步 job 渲染 |
| `backend/app/workers/export_jobs.py` | Redis/RQ 导出 worker 入口 |
| `backend/app/services/ai_jobs.py` | `AIJobRuntime` 服务，负责任务创建、幂等、活动上限、状态/心跳、取消、重试、失联检测和 Graph 依赖装配 |
| `backend/app/workers/ai_jobs.py` | 独立 `edunova_ai` Redis/RQ worker 入口 |
| `backend/app/api/v1/ai_jobs.py` | AI 任务列表、详情、SSE、取消和重试接口 |
| `backend/app/api/v1/tutor.py` | `/api/v1/tutor/sessions` 受保护会话接口 |
| `backend/app/api/v1/materials.py` | `/api/v1/materials/*` 和 `/api/v1/courses/{course_id}/materials` 受保护资料接口 |
| `backend/app/api/v1/courses.py` | `/api/v1/courses/*`、同步 `/from-materials` 和异步 `/from-materials/jobs` 受保护课程接口 |
| `backend/app/api/v1/settings.py` | `/api/v1/settings/model` 和 `/api/v1/settings/model/test` 受保护模型设置接口 |
| `backend/app/providers/openai_compatible.py` | OpenAI-compatible Provider，支持 `{base_url}/chat/completions` 非流式/流式回答和 `{base_url}/embeddings` 1536 维向量请求 |
| `backend/migrations` | Alembic 迁移环境、pgvector 扩展迁移、核心学习表迁移、学习闭环表迁移和资料库兼容迁移 |

分层职责：

| 层 | 职责 |
| --- | --- |
| API 层 | 接收请求、鉴权、参数校验、返回响应 |
| Service 层 | 课程、资料、画像、资源、路径、评估等业务逻辑 |
| Agent 层 | 多智能体状态流转和任务编排 |
| Provider 层 | 调用外部大模型和 embedding 服务 |
| RAG 层 | 切片、向量化、检索、引用组装 |
| Model 层 | 数据库实体和关系 |

约束：

- API 层不直接拼大模型提示词。
- Agent 层不直接处理 HTTP 请求。
- Provider 层不关心业务表结构。
- RAG 层必须返回可追溯引用。
- 所有写入用户数据的服务必须校验 `user_id`。

## 5. 数据架构

核心数据分为 8 类：

1. 用户与权限。
2. 课程与上传资料。
3. 知识点、知识切片和向量。
4. 学习画像与画像事件。
5. 学习路径与任务。
6. 生成资源与质量评分。
7. 练习、作答、评估报告和复习队列。
8. 对话、Agent 日志、模型设置和导出任务。
9. AI 长任务状态、进度和安全结果摘要。

数据隔离规则：

- 用户数据必须绑定 `user_id`。
- 课程内容必须绑定 `course_id`。
- 上传资料必须绑定 `user_id`。
- Phase 3 重定向后，上传资料不应强制绑定 `course_id`；资料可以独立存在于资料库，也可以通过关联表加入一个或多个课程。
- 主页对话不强制绑定 `course_id`，课程内对话必须绑定 `course_id`。
- AI 生成结果必须绑定 `trace_id`。
- 对外返回数据前必须验证当前用户是否有访问权限。

## 6. 多智能体架构

EduNova 使用 LangGraph 编排学习闭环多智能体。Service 层继续作为 API 边界和依赖装配层，认证、设置和 Dashboard 等非学习能力保持普通服务，不包装成 Agent。

核心 Agent：

| Agent | 职责 | 主要输出 |
| --- | --- | --- |
| ProfileAgent | 读取和更新学习画像 | 画像 JSON、画像事件 |
| DiagnosisAgent | 识别薄弱点和学习状态 | 诊断摘要、薄弱点 |
| CourseBuilderAgent | 从上传资料构建课程 | 课程大纲、知识点 |
| RetrieverAgent | 检索课程依据 | 引用片段 |
| ResourceAgent | 协调资源生成 | 多类型资源 |
| PathAgent | 规划学习路径 | 路径和任务 |
| TutorAgent | 个性化答疑 | 带引用回答 |
| AssessmentAgent | 评估学习效果 | 掌握度和报告 |
| ReviewAgent | 审核事实性和安全性 | 审核状态、风险提示 |

资源生成流程：

```text
用户选择课程和知识点
  ↓
ProfileAgent 读取画像
  ↓
RetrieverAgent 检索课程资料
  ↓
DiagnosisAgent 判断当前学习状态
  ↓
  PlannerAgent 形成共享生成目标
  ↓
  LangGraph Send 并行派发六类 Worker
  ↓
  AggregateAgent 汇总结构化产物
  ↓
ReviewAgent 审核内容
  ↓
保存资源、评分和 Agent 日志
  ↓
前端展示资源、引用和轨迹
```

当前真实接管生产主流程的是 `ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph`、`MaterialComparisonGraph` 和 `ExamSprintGraph`。十条 Graph 都落真实节点耗时和白名单 metadata，生成型节点均有规则与可选模型审核，失败时最多 Repair 一次。学习档案导出继续由确定性 Service 聚合并交给 Redis/RQ Worker 生成文件，不注册为生产 Graph。

### 6.1 AI 长任务运行时

Phase 17 不增加 Graph 数量，而是在 `CourseBuilderGraph` 和 `ResourceGenerationGraph` 外增加统一运行时：

```text
POST jobs + Idempotency-Key
  -> ai_jobs(queued)
  -> Redis edunova_ai queue
  -> ai-worker
  -> GraphRunner(trace_id + AgentJobContext)
  -> 独立 session 写节点进度和心跳
  -> 业务事务提交产物
  -> ai_jobs(completed / failed / cancelled)
  -> SSE，断线时 GET 轮询恢复
```

运行时只保存 ID、资源类型、目标、难度和安全结果摘要，不序列化 ORM 对象、原始资料、模型输入或思维链。取消是节点间协作式取消；持久化前会再次检查取消状态。同步建课和资源接口继续兼容旧客户端，后台接口供当前前端四个生成入口使用。学习档案与资源 PPTX 仍走独立 `edunova_exports` 队列。

后半程闭环：

```text
AssessmentGraph 规则评分
  -> 错因诊断与 PracticeAnswer 证据
  -> 合并更新 weakness_review_queue
  -> 独立 PathPlanningGraph 重排已有路径
  -> 再练习
  -> 用户主动触发 ReportGraph 聚合最近 5 次练习与趋势
```

评分、掌握度数量和趋势始终由确定性规则负责。模型只能增强题目、诊断、路径排序理由和报告叙事。路径重排发生在练习事务提交之后，失败不会回滚练习与弱点；从未创建路径时返回 `not_started`，不擅自创建默认路径。

资源 Worker：

- DocWorker：讲解文档。
- MindMapWorker：思维导图。
- QuizWorker：练习题。
- CodeWorker：代码实操案例。
- SlideWorker：结构化 PPT 页面与真实 PPTX 源数据。
- AnimationWorker：可播放的 Mermaid 教学场景，不伪装成视频。

资源内容采用 `schema_version=2`，以 `artifact.kind` 区分 `document`、`mindmap`、`quiz`、`code_lab`、`slide_deck`、`animation`，同时保存 Markdown fallback。前端 `ResourceRenderer` 按类型加载 Markmap、Mermaid、CodeMirror/Pyodide 等渲染器；PPTX 复用 Redis/RQ 导出 worker 异步生成。

## 7. RAG 与可信生成架构

RAG 流程：

```text
课程资料
  ↓
DocumentParser 文本提取
  ↓
ChunkingService 知识切片
  ↓
Phase 6.4 EmbeddingService 写入或补齐 1536 维向量
  ↓
HybridRetriever 关键词 + 向量混合检索
  ↓
Phase 5.3 课程会话保存 assistant 引用
  ↓
生成回答或资源
  ↓
ReviewAgent 审核
  ↓
带引用展示
```

当前实现状态：

- Phase 5.2 已实现 `KeywordRetriever`：基于 `knowledge_chunks.content`、`section_title`、`course_materials.filename` 和 `knowledge_points` 上下文做确定性评分。
- Phase 5.3 已让课程会话发送消息时复用该检索结果，并把引用写入 `chat_messages.citation_json`。
- Phase 6.1 已让课程会话在有引用且模型配置可用时调用 OpenAI-compatible Chat Completions 生成非流式回答，并把模型内容保存到 `chat_messages.content`，引用继续保存在 `citation_json`。
- Phase 6.3 已新增课程消息流式路径：后端通过 `event: metadata/token/done/error` 输出 SSE，完成后一次性持久化完整 assistant；失败时不保存半截内容。
- `EmbeddingService` 优先使用当前用户默认配置或服务器兜底的 OpenAI-compatible `/embeddings`。外部 embedding 成功时，课程 RAG 按用户课程、embedding 来源和模型隔离执行 pgvector cosine SQL 候选，并与中文关键词候选合并排序；首次生成的真实课程向量会提交持久化。
- 未配置外部 embedding 或 Provider 失败时只使用关键词检索，返回 `local_fallback` 或 `provider_failed`；`local-hash-1536` 不参与课程语义向量命中。API 和前端继续展示 `retrieval_mode`、`embedding_status`、`retrieval_source` 等轻量状态。
- 后续保留批量向量重建任务和讯飞原生 2560 维 Embedding 专项；ReviewAgent 已作为生成型 Graph 的审核节点接入学习闭环 trace。

可信机制：

1. 检索增强生成。
2. 引用来源绑定。
3. ReviewAgent 审核。
4. 置信度和资料不足提示。
5. 用户反馈和学习证据链。

引用字段至少包含：

- `chunk_id`。
- `material_id`。
- `source_title`。
- `page_number` 或 `section_title`。
- `content_preview`。

## 8. 上传资料建课架构

上传建课流程：

```text
上传文件
  ↓
格式校验
  ↓
保存文件
  ↓
解析文本
  ↓
CourseBuilderAgent 抽取课程结构
  ↓
生成章节和知识点
  ↓
切片与向量化
  ↓
生成课程概览
  ↓
PathAgent 生成初始路径
```

进度状态：

- `uploaded`。
- `parsing`。
- `building_course`。
- `chunking`。
- `embedding`。
- `path_generating`。
- `completed`。
- `failed`。

长任务进度先使用 Redis 保存，前端通过轮询或 SSE 获取。

## 9. 模型 Provider 架构

Provider 抽象目标能力：

- `chat_completion`。
- `stream_chat_completion`。
- `embedding`。
- `model_list`。
- `health_check`。

Phase 6.1 已实现 OpenAI-compatible Chat Completions 第一版，Phase 6.3 已实现 OpenAI-compatible streaming 解析，Provider 会在请求 `{base_url}/chat/completions` 时附带 `stream=true` 并解析 `data: {...}` 和 `[DONE]`。Phase 6.4 已实现 OpenAI-compatible embeddings：请求 `{base_url}/embeddings` 时携带 `input`、`model` 和 `dimensions=1536`，若服务不支持 `dimensions` 会重试一次不带该字段，返回向量长度不等于 1536 时拒绝写入。Phase 6.2 已把设置页从一人一套配置升级为“配置列表 + 当前编辑面板”。设置页支持：

- 多套用户个人配置，互相隔离保存和测试。
- Provider 预设，首位为讯飞星火 Spark，OpenRouter 不再作为可见预设。
- Base URL。
- API Key / APIPassword。
- 回答模型。
- Embedding 模型字段，折叠在高级项中；Phase 6.4 起用于课程知识库向量化，缺省时自动使用显式本地 fallback。
- 指定配置的连通性测试。
- 默认配置选择。
- 学生账号昵称通过 `PATCH /auth/me` 真实保存，并同步到侧栏账号入口；邮箱、角色和 starter mode 保持只读。
- 隐私与数据边界作为只读说明展示，学习档案导出仍从报告页按课程生成。

配置解析优先级：

```text
当前用户默认有效配置 -> .env 的 SYSTEM_MODEL_* -> 未配置提示
```

用户 API Key 使用 `MODEL_SETTINGS_ENCRYPTION_KEY` 派生的 Fernet 加密后保存到 `model_settings.api_key_ciphertext`。每条用户配置单独保存密钥密文、测试状态和默认标记；`GET /settings/model/configs` 只返回配置摘要、脱敏 Key、服务器兜底摘要和默认配置 id，不返回明文 Key。旧 `/settings/model` 仍作为兼容接口读取或更新当前默认配置。设置页 Provider 预设首位是讯飞星火 Spark，聊天实际走 OpenAI-compatible Chat Completions；embedding 实际走 OpenAI-compatible Embeddings。讯飞原生 Embeddingp/Embeddingq 因独立授权、签名鉴权和 2560 维输出，仍放到后续专项。

Phase 18 后，个人配置只有在字段不完整时才沿用现有服务器配置兜底；已经对个人配置发起的请求发生超时、限流或服务故障时，只在同一配置内有限重试，不把学习内容自动发送给另一 Provider。普通调用与 Embedding 最多 3 次，流式调用只允许在首 token 前重试。Redis 暂不可用时限流与熔断 fail-open，但模型 HTTP 超时、Graph fallback 和安全审计边界继续生效。

降级策略：

- 用户 Key 优先。
- 用户 Key 不可用时可使用系统 Key。
- 模型不可用时使用明确标记的确定性 fallback，不伪装 Provider 成功。
- 所有 fallback 内容必须显式标记。
- 课程会话命中引用但模型未配置时保留引用并提示未配置；模型超时、失败或流式中断时不写入半截 assistant 消息。

## 10. 安全与隐私架构

安全规则：

- 密码使用 bcrypt 哈希。
- 登录使用 JWT。
- API Key 不明文写入日志。
- 前端仅显示脱敏 Key。
- 上传文件按用户目录隔离。
- 所有资源访问校验所有权。
- 提示词注入内容不得覆盖系统安全规则。
- `.env`、上传文件、日志和缓存不提交 Git。

日志规则：

- 记录 trace_id、状态、耗时、摘要。
- 不记录完整 API Key。
- 不记录用户上传资料的敏感原文到系统日志。
- Agent 日志保存摘要和引用，不保存秘密配置。

## 11. 部署架构

Docker Compose 服务：

| 服务 | 作用 |
| --- | --- |
| frontend | 构建并托管前端静态资源 |
| backend | FastAPI 服务 |
| postgres | PostgreSQL + pgvector |
| redis | 任务进度、缓存、限流 |
| nginx | 统一入口，`/api/` 转发后端，其余请求转发前端 |

默认访问：

```text
http://localhost:8080
http://localhost:8080/api/health
```

环境变量通过 `.env` 管理，仓库只提交 `.env.example`。

## 12. 错误处理

错误响应统一包含：

- `code`：机器可读错误码。
- `message`：用户可读说明。
- `trace_id`：排查用追踪编号。
- `details`：可选细节。

典型错误：

| 场景 | 处理 |
| --- | --- |
| 未登录 | 返回 401 |
| 无权限访问他人数据 | 返回 403 或 404 |
| 上传格式不支持 | 返回 400 并说明支持格式 |
| 模型服务失败 | 返回可恢复错误或降级提示，不写入半截回答，不伪装成真实模型输出 |
| 资料不足 | 返回低依据提示 |
| 长任务失败 | 保存失败状态和错误摘要 |

## 13. 架构验收标准

架构实现达到以下条件，才算第一版可提交：

1. 前后端分层清晰，接口稳定。
2. 核心数据表按用户和课程隔离。
3. RAG 检索能返回引用来源。
4. Agent 流程能记录 trace。
5. 大模型 Provider 可替换。
6. 示例课程和确定性 fallback 能稳定跑通核心链路。
7. Docker Compose 能启动核心服务。
8. 主要设计能在答辩时用图和日志解释清楚。
