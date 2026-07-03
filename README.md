# EduNova

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

## 当前阶段

当前已完成前期基础建设、后端最小骨架、Docker 前端静态服务与 Nginx 统一入口草案、核心课程数据基础、学习闭环数据库表基础、Phase 3 前端学习空间骨架、Phase 4.1 真实认证闭环、Phase 4.2 真实学习空间首页总览、Phase 4.3 主页会话与消息持久化和 Phase 4.4 真实资料库上传与列表闭环。前端已从“静态壳子”推进到具备登录注册入口、注册时空白/人工智能导论示例课程选择、受保护路由、AI 对话主页、主页全局历史、全应用贴边可收起侧栏、侧栏账号入口、输入区文件上传、资料库浮层、最近学习轻量列表、课程空间静态壳子、独立学习路径页、融入背景的文件库式资料库、文档/图片筛选、资源工坊、学习画像、AI 辅导、练习、报告、设置核心页面骨架、生成课程浮层、上传建课进度轨道、克制状态信号层、界面文案减法、本地交互反馈、P3.15 可用性收口、P3.16 Phase 4 前口径对齐和 API 合同模块的可扩展基础。Phase 4.1 已把本地预览登录注册替换为后端注册、登录、读取当前用户、退出和受保护路由拦截；Phase 4.2 已把 `/app` 首页最近课程、资料库弹层列表和主页历史切到受保护的 `/api/v1/dashboard/summary`，不再用前端假课程伪装真实数据；Phase 4.3 已把 `/app` 主页首次发送、连续追问、左侧历史切换和刷新保留接到 `/api/v1/tutor/sessions` 真实会话与消息数据；Phase 4.4 已把主页上传、资料库列表、资料详情、解析进度和课程资料关联接到当前用户私有资料库；后续继续接入真实从资料生成课程、RAG、多智能体和学习评估。

## 文档入口

| 文档 | 说明 |
| --- | --- |
| [赛题原文](docs/软件杯A3赛题.txt) | A3 赛题要求 |
| [仓库规则](AGENTS.md) | 编码、文档同步、Git、密钥和完成定义 |
| [产品设计](docs/superpowers/specs/2026-07-01-edunova-product-design.md) | EduNova 做什么 |
| [前端与交互设计基线](docs/UI_UX_DESIGN.md) | Phase 3 前端设计方向、页面结构和验收标准 |
| [前端路由与入口体验设计](docs/FRONTEND_ROUTING_DESIGN.md) | 登录、注册 starter mode、首次进入和路由保护 |
| [实施计划](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md) | EduNova 怎么开发 |
| [中文阅读版](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md) | 实施计划中文导读 |
| [需求规格](docs/REQUIREMENTS.md) | 功能范围和验收标准 |
| [架构设计](docs/ARCHITECTURE.md) | 系统模块和技术架构 |
| [API 设计](docs/API.md) | 前后端接口约定 |
| [数据库设计](docs/DATABASE_DESIGN.md) | 数据表和关系 |
| [测试计划](docs/TEST_PLAN.md) | 测试范围和验收流程 |
| [安全基线](docs/SECURITY.md) | 账号、密钥、上传资料、RAG、日志和权限安全 |
| [风险登记册](docs/RISK_REGISTER.md) | 项目风险、触发信号和应对策略 |
| [部署说明](docs/DEPLOYMENT.md) | Docker Compose 和数据库迁移说明 |
| [项目看板](docs/PROJECT_BOARD.md) | 当前进度和下一步 |

## 第一版目标

- 学生注册登录。
- 对话式 8 维学习画像。
- 内置人工智能导论课程。
- 上传 PDF、PPTX、DOCX、Markdown、TXT 自动建课。
- RAG 引用检索。
- 多智能体协作生成 5 类资源。
- 个性化学习路径。
- AI 辅导和苏格拉底追问。
- 练习评估、掌握度地图、薄弱点复习队列。
- 期末冲刺和资料对比。
- Markdown 学习档案导出。
- 演示模式。
- Docker Compose 部署。

## 编码规则

- 所有文本文件使用 UTF-8 无 BOM。
- 禁止 UTF-16、GBK。
- 中文直接写入，不使用 `\uXXXX`。
- 不提交真实 `.env`、API Key、上传文件和缓存。

## 开发状态

当前 Phase 0 到 Phase 3 已补齐进入真实接口阶段前的主要地基，Phase 4.1 已补齐真实认证第一刀，Phase 4.2 已补齐首页真实总览第一刀，Phase 4.3 已补齐主页会话持久化第一刀，Phase 4.4 已补齐真实资料库第一刀。FastAPI 最小应用、`/api/health` 健康检查、`/api/v1/auth/register`、`/api/v1/auth/login`、`/api/v1/auth/me`、`/api/v1/auth/logout`、`/api/v1/dashboard/summary`、`/api/v1/tutor/sessions`、`/api/v1/materials/upload`、`/api/v1/materials`、`/api/v1/materials/{material_id}`、`/api/v1/materials/{material_id}/progress`、`/api/v1/courses/{course_id}/materials`、pytest 测试、编码检查、Docker Compose 草案、PostgreSQL、Redis、backend、frontend 静态服务、Nginx 统一入口、SQLAlchemy 数据库入口、Alembic 迁移基线、pgvector 扩展迁移、第一批核心业务表、独立资料库表、课程资料关联表、学习画像/路径/资源/Agent/练习/报告/对话/模型设置等学习闭环表基础和人工智能导论内置课程包已经实现。

Phase 3 前端学习空间骨架已经落地：`frontend/` 使用 React、TypeScript、Vite、Tailwind CSS v4、React Router、Zustand、React Query、Motion、Radix、React Flow、ECharts、Mermaid、Markmap、Vitest 和 ESLint。当前已实现登录页、注册页、受保护应用路由、GPT 式贴边主页侧栏、可收起主页历史、侧栏账号入口、AI 学习对话主页、输入区资料库浮层入口、输入区文件上传入口、联网搜索与深度思考激活态、语音按钮、最近学习轻量列表、发送后主页对话态、底部学习输入区、课程空间静态壳子、独立 `/app/path` 学习路径页、从资料生成课程浮层、首次进入引导，以及融入背景的文件库式资料库、文档/图片筛选、资源工坊、学习画像、AI 辅导、练习、报告、设置等学生端核心页面骨架；受保护应用路由已统一到同一套贴边工作区外壳，普通路由显示主页全局历史，课程空间显示课程内历史，资料库、课程空间、资源工坊、画像、辅导、练习、报告和设置不再保留旧顶部导航。P3.11 已继续补齐前端本地交互闭环：课程内提问可发送并写入课程历史，资源工坊可按知识点和资源类型生成本地队列与输出，学习画像可编辑目标和追加画像证据，练习提交后出现批改状态，报告导出出现准备状态，设置可编辑供应商、工具开关和昵称，命令栏与侧栏 fallback 也有可见反馈。P3.12 已开始精修主页对话体验：发送主页问题后会写入并高亮左侧历史，连续追问会留在当前主页会话内，侧栏历史搜索可按关键词过滤，首页提供轻量快捷学习建议，AI 回答下方可切换查看来源、学习路径和思考过程摘要；桌面端采用固定视口，左侧历史列表内部滚动，右侧主区域负责滚动并把滚动条留在右侧边缘，消息正文保持可读限宽，输入区保持在底部。注册页支持选择空白开始或复制「人工智能导论」示例课程：空白账号进入后没有内置课程和资料，示例账号进入后带人工智能导论课程与样例资料。

本阶段补齐了前端 API 合同模块、学习空间短状态设计、课程空间壳子、学生端核心页面骨架和交互骨架：`frontend/src/api/` 已按 `docs/API.md` 拆出 auth、dashboard、courses、materials、profiles、resources、paths、tutor、practice、reports、demo、settings 等模块，Axios 默认对齐 `/api/v1`；学习主页、资料库、资源工坊、课程空间、画像、辅导、练习、报告和设置已展示资料入库、文件列表、生成队列、画像证据、引用来源、练习反馈、掌握度地图、导出档案和隐私设置边界。上传资料、选择资料、联网搜索、深度思考、生成课程，课程内发送、主页回答展开、课程回答展开、知识点详情、辅导模式、练习提交、资料引用、资源生成、画像更新、报告导出、设置保存和命令栏等入口已经有自然反馈，避免前端骨架出现明显空按钮。上一版“学习操作系统画布 + 流程轨道 + 状态信号层”已迁入课程空间、资料库或 AI 回答展开区素材，不再作为 `/app` 首页主结构；`/app` 当前采用贴左边缘的主页侧栏、可收起历史、可搜索历史、底部账号入口、较轻的中心输入框、最近学习列表和微动效信号线，发送主页问题后会进入对话态、把输入区固定到下方，连续追问只追加到当前会话，不重复生成左侧历史，右侧主区域承担滚动并保持消息正文限宽，并在回答下方提供来源、学习路径和思考过程的轻量展开信息；输入框 Enter 发送，Shift+Enter 换行。Phase 4.1 已接入真实后端认证：登录页调用 `/auth/login` 写入 JWT session，注册页调用 `/auth/register` 后自动登录，注册 `blank` 不创建课程资料，注册 `ai_intro` 会把“人工智能导论”课程、资料、知识点和知识切片复制到当前用户自己的空间。Phase 4.2 已接入真实后端首页总览：`/app` 用 React Query 调用 `/dashboard/summary`，左侧主页历史、最近学习和主页资料库浮层资料来自当前用户数据；blank 用户保持空状态，ai_intro 用户显示自己空间里的人工智能导论。Phase 4.3 已接入真实主页会话持久化：`/app` 首次发送调用 `/tutor/sessions` 创建 home session，连续追问复用当前 session，点击左侧历史从后端读取 messages，发送失败会提示并保留输入；当前 assistant 回复仍为模板占位，不调用真实 AI/RAG。Phase 4.4 已接入真实资料库：`/app` 上传按钮调用 `/materials/upload`，成功后刷新 `/dashboard/summary`；`/app/library` 调用 `/materials` 渲染当前用户资料，支持文档/图片筛选、搜索、详情反馈和上传刷新；`.txt`、`.md` 轻解析为已完成，PDF/DOCX/PPTX/图片仅入库，图片提示“仅入库，暂不做 OCR”。真实 AI/RAG、OCR、PDF/PPT/DOCX 深度解析、真实从资料生成课程、资源生成、报告导出、多智能体真实任务和设置持久化仍属于后续阶段。

P3.15 继续收口前端可用性：主页回答下方的来源、学习路径和思考过程默认折叠，点击后才展开，避免抢占对话主体；资料库浮层和资料库页面在未选择资料时禁用“作为本次对话参考”和“创建课程草案”等主操作；从资料库进入生成课程时只保留一个上层浮层，不再出现资料库弹窗和建课弹窗叠在一起；创建课程草案后关闭浮层并给出轻量反馈；资源工坊去掉输出区重复生成入口，只保留清晰的主操作。

P3.16 完成 Phase 4 前口径对齐：登录页不再预填 demo 邮箱和密码，资源工坊五类资源收束为讲解、练习、思维导图、代码实操和 PPT 大纲，课程空间 Agent 文案统一使用 PathAgent，图片资料明确“仅入库，暂不做 OCR”，并清理普通路由外壳中不再使用的说明字段。

## 本地后端验证

创建虚拟环境并安装依赖：

```powershell
py -3.12 -m venv .venv
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:PIP_PROGRESS_BAR='off'
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

运行检查：

```powershell
.\scripts\test.ps1
```

启动后端：

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## Docker Compose 骨架验证

当前 Compose 草案包含：

- PostgreSQL + pgvector。
- Redis。
- FastAPI backend。
- React 前端生产静态服务，容器内部供 Nginx 访问。
- Nginx 统一入口，默认宿主机端口 `8080`。

校验配置：

```powershell
docker compose config
```

启动并构建：

```powershell
docker compose up --build -d
```

停止：

```powershell
docker compose down
```

当前已验证 Compose 配置可解析，服务包含 `postgres`、`redis`、`backend`、`frontend` 和 `nginx`；后端直连健康检查 `http://127.0.0.1:8000/api/health` 和 Nginx 统一入口 `http://127.0.0.1:8080/health`、`http://127.0.0.1:8080/api/health` 都属于当前部署验收口径。后端健康检查返回：

```json
{"status":"ok","service":"edunova-api"}
```

## 数据库迁移

当前 Alembic 配置文件位于 `alembic.ini`，迁移目录位于 `backend/migrations`。

启动 PostgreSQL 后运行迁移：

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic upgrade head
```

当前首条迁移会启用 pgvector：

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

第二条迁移会创建学生学习主链路的第一批核心表：

```text
users
courses
course_enrollments
course_materials
knowledge_points
knowledge_chunks
```

第三条迁移会创建后续学习闭环所需的基础表：

```text
student_profiles
profile_events
learning_paths
learning_tasks
generated_resources
resource_quality_scores
agent_run_logs
practice_sessions
practice_answers
assessment_reports
weakness_review_queue
chat_sessions
chat_messages
model_settings
```

第四条迁移会为用户表补充注册初始化方式：

```text
users.starter_mode
```

第五条迁移会创建独立个人资料库和课程资料关联表，并把已有 `course_materials` 兼容复制进去：

```text
materials
course_material_links
```

导入内置课程包：

```powershell
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
```

当前内置课程包包含 12 个知识点和 24 个基础资料切片，覆盖搜索、知识表示、机器学习、神经网络、自然语言处理、计算机视觉、多智能体和 AI 伦理安全。

## 本地前端验证

安装依赖后运行：

```powershell
cd frontend
pnpm install
pnpm lint
pnpm test
pnpm build
cd ..
```

启动前端开发服务器：

```powershell
cd frontend
pnpm dev
```

默认访问：

```text
http://127.0.0.1:5173
```

前端开发服务器已配置 `/api` 代理，默认转发到 `http://127.0.0.1:8000`。本地验收真实登录注册时，需要同时启动后端；如后端端口变化，可设置 `VITE_API_PROXY_TARGET`。
