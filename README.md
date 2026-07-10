# EduNova

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

## 当前阶段

当前最新完成到 **Phase 13 多模态资源生产化**。Phase 计划继续以 `docs/superpowers` 原始实施计划为准；Phase 7 已按“对话式学习画像”主线收口，Phase 8 已完成 Agent trace 查询与课程资源生成，Phase 9 到 Phase 12 已完成路径、练习评估、报告、冲刺、资料对比和学习档案导出；Phase 13 已让主页问答、课程问答和资源生成进入真实 LangGraph 编排，并补齐资料级 RAG、PDF/DOCX/PPTX 解析、主页工具、异步导出以及六类结构化多模态资源。

LangGraph 现在接管学习闭环生产编排：画像、资料建课/对比、课程问答、弱点识别、资源生成、学习路径、期末冲刺、练习评估、学习报告和学习档案导出都会生成或携带安全 `agent_trace_id`。认证、设置、Dashboard 等非学习 Agent 能力仍保持普通服务，不伪装成智能体。

已经具备的主链路：

- 真实注册、登录、退出和受保护路由。
- 主页真实总览、主页会话、主页消息持久化和通用模型回答。
- 当前用户个人资料库上传、列表、详情和进度查询。
- 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料生成真实课程结构；`.doc`、`.ppt`、图片和扫描件不伪装解析，图片与扫描件明确提示暂不支持 OCR。
- 课程知识点、知识切片、课程内历史和引用持久化。
- 课程空间真实模型 RAG 回答、SSE 流式输出、刷新恢复和双模式前端。
- 真实 8 维学习画像、画像对话更新、画像事件列表和课程问答弱点候选事件。
- 学习画像与课程学习状态的边界已经明确：用户级画像只保留一份，课程级弱点、路径和复习队列按课程聚合。
- `/courses/{course_id}/learning-state` 已实现课程级学习状态第一刀，可把课程问答弱点候选事件同步为 `pending` 待确认复习项，并在课程空间展示待复习弱点摘要。
- 课程级弱点复习项已支持确认、开始、完成和软忽略状态流转；软忽略项不在主列表展示，但继续参与去重。
- `/agents/traces/{trace_id}` 已实现当前用户 Agent 轨迹查询，响应包含 `workflow`、`artifact_type`、`artifact_id` 和白名单 metadata；课程空间“课堂协作轨迹”读取真实 trace 或真实空状态。
- `/resources/generate` 已实现讲解、思维导图、练习、代码实操、PPT、动画图解六类结构化课程资源；`ResourceGenerationGraph` 通过独立 Worker 并行生成并执行规则与模型审核。资源工坊和课程空间可直接渲染 Markmap、交互练习、浏览器 Python、PPT 页面和 Mermaid 动画，PPT 可通过 Redis/RQ 异步生成真实 `.pptx`。
- `/paths/generate`、`/paths/current` 和 `/paths/tasks/{task_id}` 已实现课程级学习路径生成、当前路径读取和任务状态更新；`/app/path` 已接入真实课程、任务、路径依据和掌握度图。
- `/courses/{course_id}/mastery-map` 已实现规则掌握度图，`/courses/{course_id}/learning-state` 已返回真实 `path_summary`、`mastery_summary`、弱点推荐资源和下次复习时间。
- `/practice/sessions` 和 `/practice/sessions/{session_id}/answers` 已实现真实课程练习创建、作答提交和确定性批改；错题或低分题会以 `practice_assessment` 来源反哺课程级弱点队列和掌握度图。
- `/reports/generate` 和 `/reports/latest` 已实现课程学习报告生成与读取；`/exports/learning-dossier` 保留课程级 Markdown 同步导出兼容接口，`/exports/learning-dossier/jobs`、`/exports/{job_id}` 和 `/exports/{job_id}/download` 已实现 Markdown/PDF/DOCX 异步学习档案导出；`/app/reports` 展示真实分数、掌握度更新、薄弱点、证据摘要和下一步建议，并可选择格式下载学习档案。
- `/exam-sprint/plans` 已实现期末冲刺计划生成和读取；复用 `learning_paths` / `learning_tasks`，用 `sprint_active` / `sprint_archived` 避免影响普通学习路径，`/app/path` 可生成并展示每日任务、高频点、薄弱点、必刷题、易错提醒和推荐资源。
- `/materials/compare` 已实现同课程资料对比第一刀；`/app/library` 可选择已绑定课程的两份以上已解析资料，展示重复重点、疑似考点、单资料独有点、试题独有点、遗漏复习点、优先复习顺序和安全引用摘要。
- `/app/tutor` 已收敛为课程辅导入口，真实提问统一进入课程空间。
- 多套个人模型配置、默认配置切换、服务器 `.env` 兜底。
- OpenAI-compatible Embeddings 与 `local-hash-1536` 本地 fallback。
- Phase 12.2 已补交付基线文档、测试报告、用户指南、开源说明、答辩问答、AI 辅助开发说明和 MIT 许可证。

主页回答已由 `HomeTutorGraph` 接管，按需检索当前用户选中资料的相关切片、Tavily-compatible 联网结果和安全深度规划，并通过 SSE 展示状态、真实来源、增量 Markdown、Review/Repair 和九节点安全 trace；未配置搜索 Key 时 warning 只进入来源/轨迹区，不伪造网页来源。主页语音输入和朗读使用浏览器 Web Speech API，不上传音频。课程空间继续使用严格课程引用、混合检索和流式 RAG。课程问答中的明确困惑信号会沉淀为隐私安全的画像候选事件，并通过课程学习状态同步为待确认复习项；这仍是“待确认/待复习”，不是已完成正式诊断。学生确认后才进入待复习、复习中或已完成语义，Phase 9 路径生成只消费已确认/复习中的弱点，不直接消费 `pending` 候选项。后续不会为每门课复制完整画像，而是通过课程级学习状态聚合目标、薄弱点、掌握度、复习队列和路径依据。

还没有进入的能力：

- OCR 和图片题目识别。
- 讯飞原生 Embeddingp/Embeddingq。
- 个人全局资源生成入口和资源版本化编辑；当前只有 PPTX 文件渲染进入异步任务，结构化资源生成仍为同步 Graph。
- 资料对比结果持久化、资料对比与期末冲刺联动、错题驱动深度薄弱点追溯。
- 完整浏览器 E2E 自动化套件和 Phase 13 产品打磨专项。

详细状态见 [docs/STATUS.md](docs/STATUS.md)，后续任务看 [docs/PROJECT_BOARD.md](docs/PROJECT_BOARD.md)。

## 文档入口

| 文档 | 说明 |
| --- | --- |
| [当前状态](docs/STATUS.md) | 当前完成到哪里、能用什么、还缺什么 |
| [项目看板](docs/PROJECT_BOARD.md) | 下一步优先级、里程碑和风险 |
| [赛题原文](docs/软件杯A3赛题.txt) | A3 赛题要求 |
| [仓库规则](AGENTS.md) | 编码、文档同步、Git、密钥和完成定义 |
| [需求规格](docs/REQUIREMENTS.md) | 功能范围和验收标准 |
| [架构设计](docs/ARCHITECTURE.md) | 前后端、后端分层、RAG、模型和部署架构 |
| [API 设计](docs/API.md) | 前后端接口约定 |
| [数据库设计](docs/DATABASE_DESIGN.md) | 数据表、字段和关系 |
| [RAG 检索设计](docs/RAG_DESIGN.md) | 课程知识库、Embedding fallback、混合召回和引用字段 |
| [前端与交互设计基线](docs/UI_UX_DESIGN.md) | 页面结构、视觉方向、交互规则和验收标准 |
| [前端路由设计](docs/FRONTEND_ROUTING_DESIGN.md) | 登录、注册、应用路由、课程空间和路由保护 |
| [课程空间双模式设计](docs/COURSE_SPACE_DESIGN.md) | 课程问答模式、学习模式、引用层和后续改造顺序 |
| [测试计划](docs/TEST_PLAN.md) | 测试范围、自动化验证和浏览器验收 |
| [安全基线](docs/SECURITY.md) | 账号、密钥、上传资料、RAG、日志和权限安全 |
| [部署说明](docs/DEPLOYMENT.md) | 本地开发、Docker Compose、环境变量和迁移 |
| [风险登记册](docs/RISK_REGISTER.md) | 项目风险、触发信号和应对策略 |
| [Agent 设计说明](docs/AGENT_DESIGN.md) | 多智能体角色、trace 白名单和失败恢复 |
| [开发指南](docs/DEVELOPMENT_GUIDE.md) | 本地开发、分支、测试、文档同步和浏览器验收 |
| [开源说明](docs/OPEN_SOURCE_NOTICE.md) | MIT 协议、第三方依赖、密钥和隐私边界 |
| [答辩问答](docs/DEFENSE_QA.md) | 赛题、RAG、多智能体、安全、部署和后续打磨问答 |
| [开发报告](docs/DEVELOPMENT_REPORT.md) | 系统设计、阶段成果、核心创新和当前限制 |
| [测试报告](docs/TEST_REPORT.md) | 自动化测试、Docker、浏览器验收和证据索引 |
| [用户指南](docs/USER_GUIDE.md) | 学生端使用流程 |
| [AI 辅助开发说明](docs/AI_CODING_USAGE.md) | AI Coding 使用边界、人工审查和隐私规则 |
| [Phase 12.2 验收证据](docs/evidence/PHASE_12_2_ACCEPTANCE.md) | 当前交付基线的验证命令和浏览器验收记录 |
| [产品设计](docs/superpowers/specs/2026-07-01-edunova-product-design.md) | 产品定位和设计原始稿 |
| [实施计划](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md) | 阶段路线和实现计划原始稿 |
| [中文阅读版](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md) | 实施计划中文导读 |

## 第一版完整目标

- 学生注册登录。
- 对话式 8 维学习画像。
- 内置人工智能导论课程。
- 上传资料自动建课。
- RAG 检索和引用展示。
- 多智能体协作生成学习资源。
- 个性化学习路径。
- AI 辅导和苏格拉底追问。
- 练习评估、掌握度地图和薄弱点复习队列。
- 期末冲刺和资料对比。
- Markdown/PDF/DOCX 学习档案异步导出，旧 Markdown 同步接口保留兼容。
- 快速演示通过注册页示例课程模式完成；独立共享 demo reset 不作为当前主线。
- Docker Compose 部署。

当前代码已经具备第一版主学习闭环和交付基线，但仍不是完整商业产品。不要把“第一版目标”误读成 OCR、扫描件解析、旧版 Office 格式解析、教师端和完整 E2E 都已经完成。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、Tailwind CSS、React Router、Zustand、React Query |
| 后端 | FastAPI、SQLAlchemy、Alembic、Pydantic、PyJWT、bcrypt |
| 数据 | PostgreSQL、pgvector、Redis、本地文件存储 |
| AI | OpenAI-compatible Chat Completions、SSE、OpenAI-compatible Embeddings、本地 hash fallback |
| 工程 | Docker Compose、Nginx、pytest、Vitest、ESLint、ruff、PowerShell 检查脚本 |

## 编码规则

- 所有文本文件使用 UTF-8 无 BOM。
- 禁止 UTF-16、GBK。
- 中文直接写入，不使用 `\uXXXX`。
- 不提交真实 `.env`、API Key、JWT、上传文件和缓存。
- 涉及接口、数据库、架构、测试、部署或安全变化时必须同步文档。

## 本地后端验证

创建虚拟环境并安装依赖：

```powershell
py -3.12 -m venv .venv
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:PIP_PROGRESS_BAR='off'
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

运行完整检查：

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

启动开发服务器：

```powershell
cd frontend
pnpm dev
```

默认访问：

```text
http://127.0.0.1:5173
```

前端开发服务器已配置 `/api` 代理，默认转发到 `http://127.0.0.1:8000`。
本地验收真实登录、上传、建课和课程问答时，需要同时启动后端。

## Docker Compose 验证

当前 Compose 草案包含：

- PostgreSQL + pgvector。
- Redis。
- FastAPI backend。
- React 前端生产静态服务。
- Nginx 统一入口，默认宿主机端口 `8080`。

校验配置：

```powershell
docker compose config
```

启动并构建：

```powershell
docker compose up --build -d
```

Docker 构建上下文会忽略本地 `node_modules`、`dist`、`.vite`、`output` 等运行产物，避免把本机依赖复制进 Linux 镜像。

停止：

```powershell
docker compose down
```

统一入口：

```text
http://127.0.0.1:8080
http://127.0.0.1:8080/health
http://127.0.0.1:8080/api/health
```

## 数据库迁移

当前 Alembic 配置文件位于 `alembic.ini`，迁移目录位于 `backend/migrations`。

启动 PostgreSQL 后运行迁移：

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic upgrade head
```

如果已经启动完整 Docker 栈，也可以直接在后端容器中执行迁移：

```powershell
docker compose exec -T backend python -m alembic upgrade head
```

导入内置课程包：

```powershell
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
```

完整 Docker 栈中可以改用：

```powershell
docker compose exec -T backend python -m backend.app.cli seed-ai-intro
```

内置课程包包含 12 个知识点和 24 个基础资料切片，覆盖搜索、知识表示、机器学习、神经网络、自然语言处理、计算机视觉、多智能体和 AI 伦理安全。
