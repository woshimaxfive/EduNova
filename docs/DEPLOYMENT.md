# EduNova 部署说明

日期：2026-07-01

## 1. 当前部署范围

本文档记录 EduNova 的部署方式。当前已覆盖工程骨架、核心数据表迁移、学习闭环表基础、人工智能导论内置课程包导入命令、Phase 3 前端本地开发/构建、Phase 4.1 真实认证接口、Phase 4.2 首页真实总览接口、Phase 4.3 主页会话接口、Phase 4.4 真实资料库接口、Phase 5.1 真实规则建课接口、Phase 5.2/5.3 课程知识库检索与引用持久化、Phase 6.1 模型设置与非流式真实课程 RAG 回答、Phase 6.2 多模型配置隔离、Phase 6.3 课程问答流式输出、Phase 6.4 课程知识库 embedding 与混合检索、前端静态服务和 Nginx 统一入口草案：

- FastAPI backend。
- PostgreSQL + pgvector。
- Redis。
- React 前端静态服务。
- Nginx 统一入口。
- Alembic 迁移。
- pgvector 扩展初始化。
- 用户、课程、选课、课程资料、个人资料库、课程资料关联、知识点、知识切片、画像、学习路径、生成资源、Agent 轨迹、练习、报告、对话和模型设置表。
- 人工智能导论内置课程包导入命令。
- 注册、登录、读取当前用户和退出登录接口。
- 受保护学习空间首页总览接口 `/api/v1/dashboard/summary`。
- 受保护主页会话接口 `/api/v1/tutor/sessions`。
- 受保护资料库接口 `/api/v1/materials/upload`、`/api/v1/materials`、`/api/v1/materials/{material_id}`、`/api/v1/materials/{material_id}/progress` 和 `/api/v1/courses/{course_id}/materials`。
- 受保护课程接口 `/api/v1/courses/from-materials`、`/api/v1/courses`、`/api/v1/courses/{course_id}`、`/api/v1/courses/{course_id}/overview` 和 `/api/v1/courses/{course_id}/knowledge-points`。
- 受保护 RAG 检索接口 `/api/v1/rag/search`，支持关键词/向量混合召回和本地 fallback 状态。
- 受保护模型设置接口 `/api/v1/settings/model`、`/api/v1/settings/model/test` 和 `/api/v1/settings/model/configs` 系列接口。
- React + TypeScript + Vite 前端本地开发服务器。
- 前端 lint、Vitest 和生产构建命令。
- 前端 API 合同模块，默认请求基础路径 `/api/v1`。
- Phase 3 学生端核心页面骨架，覆盖资料库、资源工坊、学习画像、AI 辅导、练习、报告和设置。

以下能力还未接入当前部署：

- 讯飞原生 Embeddingp/Embeddingq、多智能体、OCR、PDF/PPT/DOCX 深度解析和真实资源生成业务。

这些能力会在后续阶段逐步加入，并同步更新本文档。

## 2. 前置条件

本地需要安装：

- Docker Desktop。
- Docker Compose。
- Git。
- Node.js。
- pnpm。

检查命令：

```powershell
docker --version
docker compose version
docker ps
node -v
pnpm -v
```

## 3. 环境变量

仓库提供 `.env.example` 作为模板。

本地开发时可以复制：

```powershell
Copy-Item .env.example .env
```

当前 Docker Compose 支持无 `.env` 启动；如果没有 `.env`，会使用 `docker-compose.yml` 中的安全默认值。

不要提交真实 `.env` 文件。

认证相关变量：

```text
JWT_SECRET=change-this-local-development-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

`JWT_SECRET` 在正式部署时必须替换为不可公开的强随机值。

资料库上传相关变量：

```text
MATERIAL_STORAGE_DIR=var/uploads/materials
MATERIAL_MAX_UPLOAD_MB=25
```

`MATERIAL_STORAGE_DIR` 是运行时用户资料目录，已加入 `.gitignore`。本地或 Docker 卷清空后，上传文件会随运行时数据消失，需要重新上传；生产部署后续会评估对象存储。

模型 Provider 相关变量：

```text
SYSTEM_MODEL_PROVIDER=openai_compatible
SYSTEM_MODEL_BASE_URL=https://api.example.com/v1
SYSTEM_MODEL_API_KEY=replace-with-your-own-key
SYSTEM_CHAT_MODEL=example-chat-model
SYSTEM_EMBEDDING_MODEL=example-embedding-model
MODEL_SETTINGS_ENCRYPTION_KEY=replace-with-fernet-key
MODEL_REQUEST_TIMEOUT_SECONDS=20
```

`SYSTEM_MODEL_*` 是服务器统一兜底配置，仍只保留一套；用户自己的多套配置通过 `/settings/model/configs` 保存到 `model_settings`，课程回答运行时使用当前用户默认配置，默认不存在时才回退服务器配置。`SYSTEM_EMBEDDING_MODEL` 在 Phase 6.4 后用于 OpenAI-compatible `{base_url}/embeddings`；为空或不可用时，课程知识库会显式使用 `local-hash-1536` 本地 fallback，不会阻断建课和问答。`MODEL_SETTINGS_ENCRYPTION_KEY` 必须使用 Fernet key，生产环境必须替换为不可公开的强随机值；没有该值时，后端拒绝保存用户 API Key。`.env.example` 只能保留占位值，不能提交真实模型 Key。比赛演示建议优先配置讯飞星火 Spark 的 OpenAI-compatible 地址 `https://spark-api-open.xf-yun.com/v1` 和对应聊天模型；讯飞原生 Embeddingp/Embeddingq 不在当前部署范围内，真实密钥只放 `.env` 或用户加密配置中。

## 4. 启动最小服务

校验 Compose 配置：

```powershell
docker compose config
```

构建并启动：

```powershell
docker compose up --build -d
```

查看服务：

```powershell
docker compose ps
```

健康检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8080/health
http://127.0.0.1:8080/api/health
```

预期响应：

```json
{"status":"ok","service":"edunova-api"}
```

停止服务：

```powershell
docker compose down
```

## 5. 服务说明

| 服务 | 镜像或构建 | 端口 | 说明 |
| --- | --- | --- | --- |
| `postgres` | `pgvector/pgvector:pg16` | `5432` | PostgreSQL + pgvector |
| `redis` | `redis:7-alpine` | `6379` | 缓存、进度和后续限流 |
| `backend` | `docker/backend.Dockerfile` | `8000` | FastAPI 后端 |
| `frontend` | `docker/frontend.Dockerfile` | 内部 `80` | Vite 生产构建后的静态前端，只供 Nginx 访问 |
| `nginx` | `nginx:1.27-alpine` | `8080` | 统一入口，`/api/` 转发后端，其余转发前端 |

如果本机端口已被占用，可以在 `.env` 中改为其他宿主机端口：

```text
POSTGRES_PORT=15432
REDIS_PORT=16379
BACKEND_PORT=18000
NGINX_PORT=18080
```

Docker 预览时外部统一访问 Nginx，前端容器不直接占用宿主机 `5173`，避免和 `pnpm dev` 的本地开发服务器冲突。

Compose 未固定 `container_name`，同机多个 checkout 可以通过不同项目名和端口并存。需要显式指定项目名时可使用：

```powershell
docker compose -p edunova-dev up --build -d
```

## 6. 数据库迁移

当前迁移配置：

| 文件或目录 | 说明 |
| --- | --- |
| `alembic.ini` | Alembic 根配置 |
| `backend/migrations/env.py` | 从应用配置读取 `DATABASE_URL` |
| `backend/migrations/versions` | 迁移脚本目录 |

启动 PostgreSQL 后执行：

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic upgrade head
```

当前首条迁移会执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

导入内置课程包：

```powershell
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
```

## 7. 当前验收标准

当前基础部署验收标准：

1. `docker compose config` 通过。
2. `postgres` 服务健康。
3. `redis` 服务健康。
4. `backend` 服务健康。
5. 浏览器或命令行访问 `/api/health` 返回预期 JSON。
6. `alembic upgrade head` 能完成 pgvector 扩展迁移。
7. `alembic upgrade head` 能创建第一批核心业务表和学习闭环基础表。
8. `python -m backend.app.cli seed-ai-intro` 能导入人工智能导论课程包。
9. 重复执行导入命令不会创建重复课程。
10. `frontend` 可执行 `pnpm lint`、`pnpm test` 和 `pnpm build`。
11. `frontend` 静态服务和 `nginx` 统一入口能通过 Compose 配置校验。
12. 停止服务后本地 Git 状态不出现运行产物。
13. 注册、登录、读取当前用户、退出登录和未登录受保护路由跳转可在浏览器中走通。
14. 登录后的 `/app` 首页通过 `/api/v1/dashboard/summary` 读取当前用户最近课程、主页历史、资料库摘要和空状态。
15. 登录后的 `/app` 上传资料会写入当前用户个人资料库，`/app/library` 通过 `/api/v1/materials` 读取真实资料列表。
16. 已解析 TXT/Markdown 资料可以通过 `/api/v1/courses/from-materials` 生成当前用户自己的课程结构，成功后前端进入 `/app/courses/{course_id}` 并读取真实标题和知识点。
17. `/app/settings` 可以读取模型配置摘要和多配置列表，保存个人 OpenAI-compatible 配置，设为默认、删除并测试连接；前端不显示明文 Key。
18. 课程空间命中资料引用且模型配置可用时，可以通过 `/api/v1/tutor/sessions/{session_id}/messages` 或流式接口保存真实模型回答和引用；模型未配置时显示明确提示。
19. Phase 6.4 后，课程空间命中资料问题时引用区应显示混合检索状态；没有外部 embedding 配置时应显示本地向量 fallback，刷新后消息、引用和状态仍可恢复。

当前本机已验证后端与数据库基础验收项，并验证第二条迁移可以 downgrade/upgrade 往返。2026-07-03 已补第三条学习闭环迁移、第四条 `users.starter_mode` 迁移、frontend 静态服务 Dockerfile、Nginx 统一入口配置和 Phase 4.1 真实认证闭环，并通过自动化测试确认 Compose 中存在 `frontend` 与 `nginx` 服务。Phase 3 已验证前端 lint、Vitest 和 Vite build，覆盖 AI 对话主页、课程空间路由、独立学习路径路由、学生端核心页面、学习空间路由、API 合同和上传建课状态模型；P3R3 对话主页已用本地浏览器检查桌面和移动宽度的 `/app` 首屏，无水平溢出，资料库浮层和生成课程浮层可打开且保持可读。P3.6 已用本地 Edge + Playwright 补充资料库、资源工坊、画像、辅导、练习、报告和设置在桌面与 390px 移动宽度下的可见性和无水平溢出检查。P3.8 已用 Edge + Playwright 检查分层导航：桌面顶部一级入口只保留学习空间、资料库和资源工坊，个人菜单可进入画像、报告和设置；390px 移动宽度无水平溢出；课程空间可见 AI 辅导、练习和报告行动入口。GPT 式主页壳和文件库式资料库已用 Edge + Playwright 检查：桌面端侧栏贴左边缘、可收起，侧栏个人资料/设置/退出可见，输入框宽度收窄，上传资料文件能进入本地演示资料库，资料默认未选中且点选后高亮，联网搜索可激活，Enter 发送后进入主页对话态并显示下方输入区；`/app/library` 的从资料生成课程浮层覆盖整个视口；390px 移动宽度无水平溢出。P3.9 已用 Edge + Playwright 复验登录页无共享演示学生按钮、注册页空白 starter mode、空白主页无内置课程和资料、资料库路由与课程空间路由复用贴边工作区侧栏、课程侧栏历史可切换当前线程，以及 390px 移动宽度无水平溢出。本轮又复验了资料库视觉和交互：普通路由侧栏显示主页全局历史，资料库去掉突兀硬白表格块，文档/图片筛选可用，上传资料进入列表，生成课程浮层内资料可选。P3.10 已完成界面文案减法，核心页面短标题、短说明和资源工坊短状态信号已通过测试与浏览器抽查；主页首屏解释句已移除，资料来源提示只在选择资料或开启联网后出现，并已在桌面和 390px 移动宽度下复验无水平溢出。P3.15 已用 Codex 内置浏览器复验：连续追问不重复新增历史，回答附加信息默认折叠且可展开/切换/收起，搜索历史浮层可过滤，资料库未选择资料时主按钮禁用，资料库到生成课程保持单一浮层，生成课程操作后关闭并反馈，资源工坊只保留一个生成资源按钮；390px 下 `/app` 和 `/app/library` 无水平溢出。P3.16 已用 Codex 内置浏览器复验：退出后登录页邮箱和密码为空且不显示 demo 邮箱；资源工坊五类资源为讲解、练习、思维导图、代码实操和 PPT 大纲；课程空间展开 Agent 过程后显示 PathAgent 且不显示 PlannerAgent；资料库图片资料显示“仅入库，暂不做 OCR”；390px 下 `/app/studio` 和 `/app/library` 无水平溢出。

本轮 P0-P3 收尾又用 Codex 内置浏览器复验 `/app/path`：桌面端学习路径、阶段任务、路径依据、下一步行动和开始练习入口可见；390px 移动宽度无水平溢出。Docker 预览口径同步为外部统一访问 Nginx，前端容器仅在 Compose 网络内供 Nginx 访问。

Phase 4.1 已用 Codex 内置浏览器复验真实认证主链路：桌面端注册 `blank` 后自动登录进入 `/app`，空白账号显示无课程；退出后访问 `/app` 会回到 `/login`；使用刚注册账号重新登录可进入 `/app`；390px 移动宽度注册 `ai_intro` 后进入 `/app` 并可见“人工智能导论”，移动端退出和受保护路由跳转正常，无水平溢出。

Phase 4.2 已用 Codex 内置浏览器复验真实首页总览主链路：桌面端注册 `blank` 后进入 `/app`，最近学习、主页历史和主页资料库浮层均为空，未出现旧假课程、假资料和假历史；桌面端注册 `ai_intro` 后进入 `/app`，最近学习显示当前用户空间中的“人工智能导论”，进度显示“未开始”，主页资料库浮层显示“人工智能导论内置课程包.md”且默认未选中；刷新 `/app` 后数据仍保留；退出后访问 `/app` 会回到 `/login`；390px 移动宽度登录 `ai_intro` 账号后 `/app` 无水平溢出，输入框保持在可视宽度内。

Phase 4.4 已用 Codex 内置浏览器复验真实资料库主链路：桌面端注册 `blank` 后进入 `/app`，页面无假资料；同一用户通过受保护 `/materials/upload` 上传 `.txt` 和图片后，刷新 `/app` 仍保留资料状态，主页资料库浮层显示真实 TXT 与 PNG，默认未选择资料且点选后“作为本次对话参考”启用；`/app/library` 显示真实资料列表，搜索可过滤 TXT，图片筛选只显示 PNG，图片详情反馈为“已入库。第一版不做图片 OCR，可作为资料附件保存。”；退出后访问 `/app/library` 会回到 `/login`；390px 移动宽度下 `/app` 和 `/app/library` 的 `scrollWidth` 均等于 `clientWidth`，无水平溢出。内置浏览器当前不提供直接设置本机文件到 `<input type="file">` 的能力，因此文件选择动作已补充使用本机 Chromium 真实浏览器自动化复验：注册空白账号 `real_upload_1783072093534@edunova.local`，主页真实上传 `real-browser-note-1783072093534.txt` 后资料库浮层立即出现该资料，`/app/library` 真实上传 `real-browser-board-1783072093534.png` 后列表出现该资料，图片筛选中 TXT 行数为 0，390px 下 `scrollWidth=375` 且 `clientWidth=375`。后续浏览器验收优先使用 `agent-browser`；Codex 内置浏览器用于补充可见确认、用户直接观看或 agent-browser 不可用时兜底。

Phase 5.1 已用 Codex 内置浏览器复验真实规则建课主链路：注册 `ai_intro` 账号后进入 `/app`，首页显示当前用户自己的“人工智能导论”；从主页生成课程浮层选择“人工智能导论内置课程包.md”后调用真实 `/courses/from-materials` 并跳转 `/app/courses/{course_id}`，课程标题、资料数、知识点数和知识画布来自真实课程接口；从 `/app/library` 选择同一资料生成课程也能跳转新课程空间；390px 移动宽度下课程空间 `scrollWidth=375`、`clientWidth=375`，无水平溢出；退出后访问 `/app/courses/{course_id}` 会回到 `/login`。

Phase 6.4 浏览器验收优先使用 `agent-browser`：进入已有文本课程或上传 TXT/Markdown 后建课，发送能命中资料的问题，引用区应显示“混合检索”或“本地向量”状态；刷新课程页后消息、引用和检索状态仍可恢复；桌面和 390px 移动宽度不得出现水平溢出。若没有外部 embedding 模型配置，验收重点覆盖 `local-hash-1536` fallback 的可见标识。

## 8. 前端本地运行

安装并验证：

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

当前前端登录注册已经使用真实认证接口，登录后的 `/app` 首页会通过 `/dashboard/summary` 读取当前用户的最近课程、主页历史、资料库摘要和空状态；主页消息发送会写入 `/tutor/sessions`；主页上传和 `/app/library` 会调用 `/materials` 真实资料库接口；已解析 TXT/Markdown 资料可以通过 `/courses/from-materials` 生成真实课程结构；课程空间问题会持久化真实引用，并在默认模型配置可用时生成流式真实课程 RAG 回答；Phase 6.4 后引用区会显示混合检索或本地向量 fallback 状态；`/app/settings` 可管理多套用户模型配置。本地开发时 Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。如果后端端口变化，可以设置 `VITE_API_PROXY_TARGET`。资源工坊、画像、练习和报告仍使用前端预备交互或样例数据，后续由真实业务接口逐步替换。

## 9. 后续部署计划

后续阶段将补充：

- 后端数据库连接检查。
- Docker 五服务真实启动验收截图和公网部署说明。
- 演示模式初始化命令。
- 生产部署建议。
