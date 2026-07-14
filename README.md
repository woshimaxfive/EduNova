# EduNova

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

## 当前阶段

当前已完成 **Phase 21 资料精细解析与高质量智能建课**。十条生产主链路由真实 LangGraph 编排；资料先经过章节保真的解析、质量门禁和用户目录确认，再进入章节并行智能建课。

当前十条真实生产 Graph 为 `MaterialIngestionGraph`、`ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph` 和 `MaterialComparisonGraph`。学习档案导出明确保持确定性 Service + Redis/RQ Worker，不包装成 Agent；认证、设置、Dashboard 等非学习能力同样保持普通服务。

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
- `/resources/generate` 保留同步兼容；新入口 `/resources/generation-jobs` 通过 `AIJobRuntime` 和独立 `edunova_ai` 队列执行六类 v3 结构化资源。Planner 为每类资源制定教学策略、认知层级、案例方向、证据和学习结果，六个 Worker 按互补职责生成；ReviewAgent 同时审核意图、证据、完整内容和历史差异。课程资源支持版本族、版本切换、比较、换教法和优化当前版本，任何失败都不会覆盖旧成果。
- `/paths/generate`、`/paths/current` 和 `/paths/tasks/{task_id}` 已实现课程级个性化学习路径生成、当前路径读取和任务状态更新；路径只表达学习顺序、当前任务和完成状态，不设置日期或期限。`PathPlanningGraph` 会综合画像、确认弱点、练习诊断、掌握度、资源和旧路径进度，练习回流只重排已有路径并保留已完成任务。
- `/courses/{course_id}/mastery-map` 只使用有效练习作答和课程弱点等明确证据；未评估知识点返回 `score=null`，不参与课程平均值。路径任务只表达学习进度，不再制造掌握度分数。
- `/practice/sessions` 和 `/practice/sessions/{session_id}/answers` 已由 `AssessmentGraph` 编排证据型题目和逐题诊断，支持 `adaptive` 难度；题目引用、生成模式、Prompt 版本和质量摘要可追溯，客观分数始终由规则决定。
- `/reports/generate` 和 `/reports/latest` 已由 `ReportGraph` 聚合最近 5 次练习、掌握度、弱点、路径和资源。练习会话数、已作答题数、正确题数、已评估知识点数和已完成路径任务数分别锁定，模型只能增强叙事和建议，数字矛盾必须修订或退回确定性报告。
- `/materials/compare` 已由 `MaterialComparisonGraph` 接管；每次对比保存不可变版本，可恢复最近结果、追溯真实资料分块和审核轨迹。资料对比是资料库内的独立辅助工具，不会隐式修改学习路径或练习。
- AI 辅导直接在 `/app/courses/:courseId` 课程空间内完成；已移除无独立能力的中转页，旧 `/app/tutor` 地址会回到学习主页。
- 多套个人模型配置；每套配置可组合回答、向量和重排序三个不同服务商，并为三类能力分别保存连接、加密凭证、连接验证和默认用途。新配置推荐 Spark X2-Flash 回答、讯飞 LLM Embedding 和硅基 BGE Reranker，未提供完整凭证的能力保持未启用。
- 设置中心支持回答、向量与重排序独立验证，并提供显式向量重建任务；账号体系使用独立账号和昵称，登录账号统一小写且创建后不可修改，账号区支持修改昵称和密码，密码更新后所有旧 JWT 立即失效；隐私区只说明真实的数据边界和档案导出入口。
- 模型调用采用当前配置有限重试，不在故障后自动转发到另一 Provider；失败时保留各 Graph 的确定性 fallback。
- `model_call_runs` 只记录模型名、状态、尝试次数、耗时和安全错误分类，Agent trace 可查看聚合调用摘要，不保存 Prompt 或回答正文。
- 讯飞原生 2560 维 Embedding、百炼/硅基 OpenAI-compatible Embeddings、动态 pgvector 与可选 Rerank 已接入；主页资料与课程 RAG 使用关键词 Top 30、向量 Top 30、RRF Top 20、重排序后 Top 5，任一外部能力不可用时按层降级。
- Docker Compose 新增仅内部网络可访问的 `code-verifier`。生成代码在非 root、只读文件系统、无外网和资源限制下由 Pyodide 独立 Worker 运行，只有安全策略、运行结果和预期输出全部一致时才允许保存。
- Phase 12.2 已补交付基线文档、测试报告、用户指南、开源说明、答辩问答、AI 辅助开发说明和 MIT 许可证。

主页回答已由 `HomeTutorGraph` 接管，按需检索当前用户选中资料的相关切片、Tavily-compatible 联网结果和安全深度规划，并通过 SSE 展示状态、真实来源、增量 Markdown、Review/Repair 和九节点安全 trace；未配置搜索 Key 时 warning 只进入来源/轨迹区，不伪造网页来源。主页语音输入和朗读使用浏览器 Web Speech API，不上传音频。课程空间继续使用严格课程引用、混合检索和流式 RAG。课程问答中的明确困惑信号会沉淀为隐私安全的画像候选事件，并通过课程学习状态同步为待确认复习项；这仍是“待确认/待复习”，不是已完成正式诊断。学生确认后才进入待复习、复习中或已完成语义，Phase 9 路径生成只消费已确认/复习中的弱点，不直接消费 `pending` 候选项。后续不会为每门课复制完整画像，而是通过课程级学习状态聚合目标、薄弱点、掌握度、复习队列和路径依据。

主页侧栏通过 `/tutor/sessions/history` 首批读取 30 条未归档主页会话并按需继续加载，服务端搜索覆盖标题和消息正文。主页会话保存最多 10 份已解析参考资料；确认后刷新或通过 `session_id` 恢复会话时自动恢复，建课资料选择使用独立状态，不会反向改写对话资料范围。

还没有进入的能力：

- OCR、图片题目识别、旧版 Office 和扫描件解析。
- OCR、图片题目识别之外的多模态向量检索。
- 个人全局资源生成入口；课程级结构化资源已支持后台任务与不可覆盖的历史版本，个人全局资源仍未接入。
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
- 可选的《数据结构与算法》内置课程：8 个理论章节、56 个知识点、184 个证据切片和 16 个 Python 实验。
- 上传资料自动建课。
- RAG 检索和引用展示。
- 多智能体协作生成学习资源。
- 个性化学习路径。
- AI 辅导和苏格拉底追问。
- 练习评估、掌握度地图和薄弱点复习队列。
- 资料对比与考点提炼。
- Markdown/PDF/DOCX 学习档案异步导出，旧 Markdown 同步接口保留兼容。
- 快速体验可在注册页主动选择数据结构与算法内置课程；新用户默认空白开始，不创建共享 demo 账号。
- Docker Compose 部署。

当前代码已经具备第一版主学习闭环和交付基线，但仍不是完整商业产品。不要把“第一版目标”误读成 OCR、扫描件解析、旧版 Office 格式解析、教师端和完整 E2E 都已经完成。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、Tailwind CSS、React Router、Zustand、React Query |
| 后端 | FastAPI、SQLAlchemy、Alembic、Pydantic、PyJWT、bcrypt |
| 数据 | PostgreSQL、pgvector、Redis、本地文件存储 |
| AI | Spark X2-Flash / OpenAI-compatible Chat、讯飞与兼容 Embeddings、可选 Rerank、动态 pgvector、SSE 与关键词 fallback |
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

同步内置课程包并替换旧内置课：

```powershell
.\.venv\Scripts\python -m backend.app.cli sync-builtin-courses
```

完整 Docker 栈中可以改用：

```powershell
docker compose exec -T backend python -m backend.app.cli sync-builtin-courses
```

Docker 后端会在迁移完成后自动执行该同步。课程包包含 9 份仅在课程内部可见的系统来源、56 个知识点、184 个切片和 16 个 Python 实验；不会在个人资料库创建衍生文件。课程正文和实验均为重新组织的原创表达，仓库不包含参考教材 PDF、扫描页、插图或教材代码。课程包另有逐知识点教学指引、32 条关键词 RAG 基准和 16 组可执行边界验证，详见 `docs/BUILTIN_COURSE_QUALITY.md`。

## 资料解析与智能建课

用户上传的 TXT、Markdown、PDF、DOCX 和 PPTX 会进入后台 `MaterialIngestionGraph`，依次完成页面提取、版面清理、目录识别、章节内切片、质量门禁和持久化。资料库始终只展示原文件；目录候选、页码、切片和解析诊断仅作为系统内部数据。

解析成功后资料进入“待确认”状态。用户可以在资料详情中检查目录、页码与真实切片，排除无关章节、改名、合并或拆分边界，再确认结构。只有目录已确认且质量通过的资料才能进入 `CourseBuilderGraph`。建课按章节并行分析，知识点必须绑定真实切片，并通过章节覆盖、证据完整、标题去重和先修无环等门禁后才会落库。
