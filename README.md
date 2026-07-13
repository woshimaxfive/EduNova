# EduNova

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

## 当前阶段

当前最新完成到 **Phase 18 AI 执行可靠性与质量评测**。九条学习主链路继续由真实 LangGraph 编排；`ModelExecutionRuntime` 统一处理同配置重试、Redis 并发限制、熔断、流中断、长任务取消和隐私安全调用审计，`AIJobRuntime` 继续负责智能建课与六类资源生成的后台执行。

当前九条真实生产 Graph 为 `ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph` 和 `MaterialComparisonGraph`。学习档案导出明确保持确定性 Service + Redis/RQ Worker，不包装成 Agent；认证、设置、Dashboard 等非学习能力同样保持普通服务。

已经具备的主链路：

- 真实注册、登录、退出和受保护路由。
- 主页真实总览、分页历史搜索、会话级参考资料记忆、主页消息持久化和通用模型回答。
- 当前用户个人资料库上传、列表、详情和进度查询。
- 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料通过 `CourseBuilderGraph` 生成带来源覆盖、学习目标、先修关系和安全审核的课程结构；`.doc`、`.ppt`、图片和扫描件不伪装解析。
- 课程知识点、知识切片、课程内历史和引用持久化。
- 课程空间真实模型 RAG 回答、SSE 流式输出、刷新恢复和双模式前端。
- `ProfileGraph` 管理真实 8 维学习画像、逐维可信度和证据事件；显式回答立即更新，隐式学习信号满足双来源与置信度门槛后才进入长期画像。
- 学习画像与课程学习状态的边界已经明确：用户级画像只保留一份，课程级弱点、路径和复习队列按课程聚合。
- `/courses/{course_id}/learning-state` 已实现课程级学习状态第一刀，可把课程问答弱点候选事件同步为 `pending` 待确认复习项，并在课程空间展示待复习弱点摘要。
- 课程级弱点复习项已支持确认、开始、完成和软忽略状态流转；软忽略项不在主列表展示，但继续参与去重。
- `/agents/traces/{trace_id}` 已实现当前用户 Agent 轨迹查询，响应包含 `workflow`、`artifact_type`、`artifact_id` 和白名单 metadata；课程空间“课堂协作轨迹”读取真实 trace 或真实空状态。
- `/resources/generate` 保留同步兼容；新入口 `/resources/generation-jobs` 通过 `AIJobRuntime` 和独立 `edunova_ai` 队列执行讲解、思维导图、练习、代码实操、PPT、动画图解六类结构化资源。`ResourceGenerationGraph` 通过独立 Worker 并行生成并执行规则与模型审核，前端支持跨页面观察、刷新恢复、取消和失败重试。
- `/paths/generate`、`/paths/current` 和 `/paths/tasks/{task_id}` 已实现课程级个性化学习路径生成、当前路径读取和任务状态更新；路径只表达学习顺序、当前任务和完成状态，不设置日期或期限。`PathPlanningGraph` 会综合画像、确认弱点、练习诊断、掌握度、资源和旧路径进度，练习回流只重排已有路径并保留已完成任务。
- `/courses/{course_id}/mastery-map` 已实现规则掌握度图，`/courses/{course_id}/learning-state` 已返回真实 `path_summary`、`mastery_summary`、弱点推荐资源和下次复习时间。
- `/practice/sessions` 和 `/practice/sessions/{session_id}/answers` 已由 `AssessmentGraph` 编排出题和评估，支持 `adaptive` 难度；最近练习与未提交草稿可通过 URL、最近会话接口和草稿接口恢复。客观分数始终由规则决定。
- `/reports/generate` 和 `/reports/latest` 已由 `ReportGraph` 聚合最近 5 次练习、掌握度、弱点、路径和资源。分数与趋势由规则计算，模型只增强叙事和建议；报告继续由用户主动生成。学习档案同步/异步导出接口保持兼容。
- `/materials/compare` 已由 `MaterialComparisonGraph` 接管；每次对比保存不可变版本，可恢复最近结果、追溯真实资料分块和审核轨迹。资料对比是资料库内的独立辅助工具，不会隐式修改学习路径或练习。
- AI 辅导直接在 `/app/courses/:courseId` 课程空间内完成；已移除无独立能力的中转页，旧 `/app/tutor` 地址会回到学习主页。
- 多套个人模型配置；每套配置可分别填写回答与向量服务商、Base URL、Key 和模型，例如同一方案由星火回答、百炼向量检索。回答预设收录国内常用生成模型，向量预设只收录兼容当前 1536 维检索库的真实 Embedding 服务，两套清单彼此独立。回答默认与向量默认仍可分别选择，缺失用途独立回退服务器 `.env`。
- 设置中心将回答模型与向量模型分开测试并持久保存安全结果；账号区支持修改昵称和密码，密码更新后所有旧 JWT 立即失效；隐私区只说明真实的数据边界和档案导出入口。
- 模型调用采用当前配置有限重试，不在故障后自动转发到另一 Provider；失败时保留各 Graph 的确定性 fallback。
- `model_call_runs` 只记录模型名、状态、尝试次数、耗时和安全错误分类，Agent trace 可查看聚合调用摘要，不保存 Prompt 或回答正文。
- OpenAI-compatible Embeddings 与 pgvector SQL cosine 候选；未配置或 Provider 失败时退回关键词检索，`local-hash-1536` 不再标记为语义命中。
- Phase 12.2 已补交付基线文档、测试报告、用户指南、开源说明、答辩问答、AI 辅助开发说明和 MIT 许可证。

主页回答已由 `HomeTutorGraph` 接管，按需检索当前用户选中资料的相关切片、Tavily-compatible 联网结果和安全深度规划，并通过 SSE 展示状态、真实来源、增量 Markdown、Review/Repair 和九节点安全 trace；未配置搜索 Key 时 warning 只进入来源/轨迹区，不伪造网页来源。主页语音输入和朗读使用浏览器 Web Speech API，不上传音频。课程空间继续使用严格课程引用、混合检索和流式 RAG。课程问答中的明确困惑信号会沉淀为隐私安全的画像候选事件，并通过课程学习状态同步为待确认复习项；这仍是“待确认/待复习”，不是已完成正式诊断。学生确认后才进入待复习、复习中或已完成语义，Phase 9 路径生成只消费已确认/复习中的弱点，不直接消费 `pending` 候选项。后续不会为每门课复制完整画像，而是通过课程级学习状态聚合目标、薄弱点、掌握度、复习队列和路径依据。

主页侧栏通过 `/tutor/sessions/history` 首批读取 30 条未归档主页会话并按需继续加载，服务端搜索覆盖标题和消息正文。主页会话保存最多 10 份已解析参考资料；确认后刷新或通过 `session_id` 恢复会话时自动恢复，建课资料选择使用独立状态，不会反向改写对话资料范围。

还没有进入的能力：

- OCR、图片题目识别、旧版 Office 和扫描件解析。
- 讯飞原生 Embeddingp/Embeddingq。
- 个人全局资源生成入口和资源版本化编辑；课程级结构化资源生成已进入后台 AI 任务，个人全局资源仍未接入。
- 学习档案导出的 Agent 化；当前确定性 Service + RQ 已满足业务需要，不列为默认开发目标。

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
- 资料对比与考点提炼。
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
| AI | OpenAI-compatible Chat Completions、SSE、OpenAI-compatible Embeddings、pgvector SQL 与关键词 fallback |
| 工程 | Docker Compose、Nginx、pytest、Vitest、Playwright、ESLint、ruff、PowerShell 检查脚本 |

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
