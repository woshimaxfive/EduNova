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

前端使用 React + TypeScript + Vite，定位为学生 AI 学习空间。具体设计基线见 [UI_UX_DESIGN.md](UI_UX_DESIGN.md)，入口与路由设计见 [FRONTEND_ROUTING_DESIGN.md](FRONTEND_ROUTING_DESIGN.md)。

第一版前端不采用后台管理式左侧菜单，不把首屏做成卡片堆。2026-07-02 P3 精修后，首页采用“贴左边缘主页侧栏 + 可收起历史对话 + 侧栏账号入口 + 中心 AI 学习入口 + 输入区资料库浮层按钮 + 最近学习轻量列表”的结构；发送主页问题后进入对话态，输入区移动到下方，靠近 ChatGPT 的对话工作方式。主页输入框已具备文件上传入口、资料库选择、生成课程入口、联网搜索激活态、深度思考激活态、语音入口和 Enter 发送/Shift+Enter 换行的前端行为。课程空间采用“课程内对话 + 今日任务 + 知识画布 + 资源工坊 + 证据层 + Agent 轨迹”的静态/半静态壳子；独立 `/app/path` 学习路径页展示阶段任务、路径依据和下一步行动，但不放到首页抢主视觉；资料库已调整为文件库式页面，按文档/图片等文件类型筛选，视觉通过半透明、细分隔线和背景模糊融入页面。P3.13 后，普通路由只保留短标题，不展示重复说明句；普通路由侧栏高亮当前页面，“新建对话”回到 `/app`；资料库上传只入库，不自动加入生成课程选择，生成课程浮层默认未选中。P3.15 后，回答附加信息默认折叠，资料库和生成课程主操作在未选资料前禁用，从资料库进入生成课程时只保留一个上层浮层，资源工坊只保留一个主生成入口。P3.9 之后受保护应用区统一使用 `AppSidebar` 贴边工作区外壳：资料库、资源工坊、画像、AI 辅导、练习、报告和设置不再保留旧顶部导航，且普通路由侧栏显示主页全局历史；课程空间复用侧栏视觉，但显示课程内历史；个人资料、设置和退出登录固定在侧栏底部；AI 辅导、练习、学习路径和报告也可从课程空间行动入口或回答展开区进入。注册页通过 `starter_mode` 决定是否复制人工智能导论示例课程，登录页不提供共享演示学生按钮。后续由真实课程、资料、RAG、画像、练习评估、报告和 Agent 数据驱动。

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
| `AppSidebar` | 受保护应用区统一贴边工作区侧栏，普通路由承载资料库、资源工坊、主页全局历史、个人资料、设置、退出登录和收起控制；课程空间承载课程内历史 |
| `HomeChat` | 总 AI 学习主页，对话可以独立存在，也可以移入某一课程 |
| `CommandBar` | 自然语言主入口，触发上传资料、选择资料、生成课程、基于资料问答和保存回答 |
| `MaterialContextPanel` | 轻量资料上下文，连接独立资料库、主页对话和课程资料 |
| `LearningCanvas` | 课程内可视化模块，展示课程焦点、知识点网络、学习路径节点、资料流入和薄弱点 |
| `SourceCluster` | 课程内展示资料源、解析状态和引用覆盖度 |
| `StudioDock` | 展示讲解、练习、思维导图、代码实操、PPT 大纲等生成产物 |
| `EvidenceLayer` | 展示引用来源、Agent 轨迹、ReviewAgent 结果、低依据提示和质量评分 |
| `AgentTimeline` | 展示多智能体步骤、耗时、状态和失败节点 |
| `MasteryVisual` | 展示画像雷达、知识点掌握状态和薄弱点复习队列 |

主要页面：

| 页面 | 作用 |
| --- | --- |
| 登录/注册 | 进入系统 |
| 学习主页 | 第一屏主体验，承载贴边可收起主页历史、侧栏账号入口、轻量输入框、发送后主页对话态、资料选择、文件上传和最近课程 |
| 资料库 | 文件库式独立资料管理，支持搜索、上传、查看引用、作为主页参考和从资料生成课程；生成课程以浮层覆盖当前页面 |
| 课程空间 | 已补前端静态/半静态壳子，承载课程内历史对话、课程资料、学习画布、资源工坊、证据层、AI 辅导、练习和报告等学习闭环入口 |
| 学习路径 | 独立路径工作区，展示阶段任务、路径依据和下一步行动，后续接 `learning_paths` 与 `learning_tasks` |
| 资源工坊 | 查看和管理生成的学习资源；当前已补资源生成工作台、生成队列和输出区 |
| 画像 | 查看学习目标、基础、节奏、薄弱点和画像证据 |
| AI 辅导 | 课程资料驱动的追问入口，展示辅导模式和引用来源 |
| 练习 | 作答、批改反馈和薄弱点复习队列 |
| 报告 | 查看画像、掌握度、薄弱点、学习报告和导出入口 |
| 设置 | 配置模型 Provider、个人信息、隐私数据边界和导出数据 |

路由结构：

| 路由组 | 路径 |
| --- | --- |
| 公开入口 | `/`、`/login`、`/register`、`/demo` |
| 应用区 | `/app`、`/app/library`、`/app/path`、`/app/courses/:courseId`、`/app/studio`、`/app/profile`、`/app/tutor`、`/app/practice`、`/app/reports`、`/app/settings` |
| 兜底 | `*` |

路由保护：

- `ProtectedRoute` 统一保护 `/app/*`。
- `PublicOnlyRoute` 处理已登录用户访问 `/login` 和 `/register`。
- API client 收到 401 后清理登录态并跳回 `/login`。
- 后续 Demo 入口由独立 service 管理，避免登录页重新堆共享演示账号逻辑。

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
| `frontend/src/api/*.ts` | 按业务域拆分的前端 API 合同模块，覆盖 auth、dashboard、courses、materials、profiles、resources、agents、paths、tutor、practice、reports、demo、settings |
| `frontend/src/features/workspace/workflowState.ts` | 上传建课生命周期和短状态信号的纯状态模型 |
| `frontend/src/pages` | 登录、注册、Demo、学习空间、资料库、学习路径、资源工坊、画像、辅导、练习、报告、设置和 404；学生端核心页面已从占位页补成可扩展工作区骨架 |
| `frontend/src/components` | `AppSidebar`、学习空间壳子、学习画布、资料源簇、AI 命令栏、资源输出区、证据层、Agent 轨迹、上传建课状态轨道、学习空间状态条和统一 `ActionNotice` 反馈层；`/app` 首页已补 GPT 式贴边侧栏、可收起历史、侧栏账号入口、AI 对话主页、输入区资料库浮层入口、文件上传入口、最近学习轻量列表、发送后对话态和生成课程浮层，回答附加信息默认折叠；`/app/library` 已改为文件库式资料管理页，资料选择和生成课程主操作具备禁用态，资料库到生成课程只保留单一上层浮层；`/app/courses/:courseId` 已组合课程空间静态壳子，资料库、课程空间、资源工坊、画像、辅导、练习、报告和设置复用同一贴边工作区视觉体系；`PageFrame` 只承担普通路由外壳，不抢占内部内容区语义 |
| `frontend/src/styles/global.css` | 视觉 token、响应式布局、深色模式、reduced motion 和 reduced transparency 基础 |

当前限制：

- Phase 4.1 已完成真实注册、登录、读取当前用户和退出闭环；注册 starter mode 已落入后端注册接口和用户初始化流程。
- 当前 `/app` AI 对话主页使用前端样例主页会话、资料库和最近课程数据；后续由 `/dashboard/summary`、主页会话、资料库和最近课程接口替换。
- 当前 `/app/courses/:courseId` 课程空间使用前端样例课程、知识点、资料、引用和 Agent 轨迹数据；后续由课程详情、RAG、资源生成和 Agent 日志接口替换。
- 当前资料库、资源工坊、画像、辅导、练习、报告和设置页面使用前端样例数据；后续由资料、画像、RAG、练习评估、掌握度报告和设置接口替换。
- 当前 P3.7 按钮反馈使用 React 本地状态和 `ActionNotice`，用于固定前端交互边界；后续接 API 时应把对应 handler 替换为 React Query mutation、轮询或 SSE 任务状态。
- 上传建课状态轨道和状态条当前使用前端样例状态，后续由 `/materials/{material_id}/progress`、`/courses/from-materials` 和长任务接口驱动。
- React Flow、ECharts、Mermaid 和 Markmap 已作为依赖准备，复杂图谱和可视化在后续阶段逐步接入。

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
| `backend/app/core/config.py` | 环境配置，读取 `DATABASE_URL` 和 `REDIS_URL` |
| `backend/app/db/base.py` | SQLAlchemy Declarative Base |
| `backend/app/db/session.py` | 数据库 engine、Session 工厂和依赖入口 |
| `backend/app/models` | 用户、课程、资料、知识点、知识切片核心模型，以及画像、路径、资源、Agent 轨迹、练习、报告、对话和模型设置基础模型 |
| `backend/app/data/builtin_courses` | 内置课程包数据 |
| `backend/app/services/course_seed.py` | 内置课程导入服务 |
| `backend/migrations` | Alembic 迁移环境、pgvector 扩展迁移、核心学习表迁移和学习闭环表迁移 |

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

数据隔离规则：

- 用户数据必须绑定 `user_id`。
- 课程内容必须绑定 `course_id`。
- 上传资料必须绑定 `user_id`。
- Phase 3 重定向后，上传资料不应强制绑定 `course_id`；资料可以独立存在于资料库，也可以通过关联表加入一个或多个课程。
- 主页对话不强制绑定 `course_id`，课程内对话必须绑定 `course_id`。
- AI 生成结果必须绑定 `trace_id`。
- 对外返回数据前必须验证当前用户是否有访问权限。

## 6. 多智能体架构

EduNova 使用 LangGraph 编排多智能体。

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
ResourceAgent 调用不同 Worker 生成资源
  ↓
ReviewAgent 审核内容
  ↓
保存资源、评分和 Agent 日志
  ↓
前端展示资源、引用和轨迹
```

资源 Worker：

- DocWorker：讲解文档。
- MindMapWorker：思维导图。
- QuizWorker：练习题。
- CodeWorker：代码实操案例。
- SlideWorker：PPT 大纲或视频脚本。

## 7. RAG 与可信生成架构

RAG 流程：

```text
课程资料
  ↓
DocumentParser 文本提取
  ↓
ChunkingService 知识切片
  ↓
EmbeddingService 向量化
  ↓
pgvector 存储
  ↓
Retriever 检索相关片段
  ↓
生成回答或资源
  ↓
ReviewAgent 审核
  ↓
带引用展示
```

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

Provider 抽象能力：

- `chat_completion`。
- `stream_chat_completion`。
- `embedding`。
- `model_list`。
- `health_check`。

第一版支持 OpenAI-compatible 接口。系统设置支持：

- 供应商名称。
- Base URL。
- API Key。
- 聊天模型。
- Embedding 模型。
- 连通性测试。

降级策略：

- 用户 Key 优先。
- 用户 Key 不可用时可使用系统 Key。
- 演示模式可使用 fallback Provider。
- 所有 fallback 内容必须显式标记。

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
| 模型服务失败 | 返回降级提示或使用 Demo fallback |
| 资料不足 | 返回低依据提示 |
| 长任务失败 | 保存失败状态和错误摘要 |

## 13. 架构验收标准

架构实现达到以下条件，才算第一版可提交：

1. 前后端分层清晰，接口稳定。
2. 核心数据表按用户和课程隔离。
3. RAG 检索能返回引用来源。
4. Agent 流程能记录 trace。
5. 大模型 Provider 可替换。
6. 演示模式能稳定兜底。
7. Docker Compose 能启动核心服务。
8. 主要设计能在答辩时用图和日志解释清楚。
