# EduNova 部署说明

日期：2026-07-01

## 1. 当前部署范围

本文档记录 EduNova 的本地开发、Docker Compose 和部署准备方式。

当前部署范围覆盖到 Phase 13.2：

- 工程骨架和 Docker Compose。
- 数据库迁移和内置课程包导入。
- 真实认证、首页、资料库、PDF/DOCX/PPTX 解析、规则建课、课程 RAG 和课程会话。
- 模型配置、课程流式回答、Embedding、混合检索和课程空间双模式前端。
- 学习画像、课程学习状态、弱点复习队列和状态流转。
- Agent trace 查询和资源生成 trace。
- 六类结构化课程资源、并行 Worker、质量审核、Markmap/Mermaid/Pyodide 和 PPTX 导出。
- 前端镜像会把 `pyodide.mjs` 与配套运行时复制到版本化目录 `/pyodide/0.29.2/`，Web Worker 直接导入自托管 loader；版本目录用于隔离 immutable 浏览器缓存。Nginx 必须保留 `.js`、`.mjs`、`.wasm`、`.json` 的正确 MIME，并按 Pyodide 官方分发兼容方式以 `application/wasm` 提供标准库 zip，同时返回 CORS、CORP 与 `nosniff` 安全头。
- 学习路径、规则掌握度图、练习评估、学习报告、期末冲刺、资料对比和 Markdown/PDF/DOCX 学习档案导出。
- 主页联网搜索、深度回答指令、浏览器语音输入/朗读和 `home_tutor` trace。
- 交付基线文档、开源说明、MIT 许可证和验收证据索引。
- 前端本地开发、生产构建和 Nginx 统一入口草案。

- FastAPI backend。
- PostgreSQL + pgvector。
- Redis。
- RQ export worker。
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
- 受保护课程接口 `/api/v1/courses/from-materials`、`/api/v1/courses`、`/api/v1/courses/{course_id}`、`/api/v1/courses/{course_id}/overview`、`/api/v1/courses/{course_id}/knowledge-points`、`/api/v1/courses/{course_id}/learning-state` 和 `/api/v1/courses/{course_id}/mastery-map`。
- 受保护 RAG 检索接口 `/api/v1/rag/search`，支持关键词/向量混合召回和本地 fallback 状态。
- 受保护模型设置接口 `/api/v1/settings/model`、`/api/v1/settings/model/test` 和 `/api/v1/settings/model/configs` 系列接口。
- 受保护画像、Agent trace、资源、学习路径、练习、报告、期末冲刺、资料对比、Markdown 同步导出和异步导出任务接口。
- React + TypeScript + Vite 前端本地开发服务器。
- 前端 lint、Vitest 和生产构建命令。
- 前端 API 合同模块，默认请求基础路径 `/api/v1`。
- 学生端核心页面，覆盖首页、资料库、课程空间（含 AI 辅导）、资源工坊、学习画像、练习、报告、学习路径和设置。

以下能力还未接入当前部署：

- 讯飞原生 Embeddingp/Embeddingq、OCR、旧版 Office 解析、扫描件解析和完整浏览器 E2E。

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

联网搜索和导出相关变量：

```text
WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_ENDPOINT=https://api.tavily.com/search
WEB_SEARCH_API_KEY=
WEB_SEARCH_MAX_RESULTS=5
EXPORT_DIR=storage/exports
EXPORT_QUEUE_NAME=edunova_exports
```

`WEB_SEARCH_API_KEY` 为空时，主页联网搜索只返回“未配置” warning，不生成假来源。Docker Compose 中 backend 和 `export-worker` 共享导出卷，确保 worker 生成的学习档案可由下载接口读取；数据库迁移由 backend 启动命令执行，`export-worker` 等 backend 健康后只消费 RQ 队列。

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

`SYSTEM_MODEL_*` 是服务器统一兜底配置，当前只保留一套。

Docker Compose 会把仓库根目录的 `.env` 作为 backend 容器的可选运行时环境文件读取，用于注入 `SYSTEM_MODEL_*`、`MODEL_SETTINGS_ENCRYPTION_KEY` 等服务器配置。`.env` 已被 `.gitignore` 忽略，不能提交真实密钥。为了避免把密钥展开到终端日志，统一验证脚本只运行 `docker compose config --quiet`。

个人模型配置通过 `/settings/model/configs` 保存到 `model_settings`：

- 课程回答优先使用当前用户默认配置。
- 用户没有默认配置时才回退服务器配置。
- 用户 API Key 使用 Fernet 加密保存。
- 接口只返回脱敏 Key，不返回明文。

`SYSTEM_EMBEDDING_MODEL` 在 Phase 6.4 后用于 OpenAI-compatible `{base_url}/embeddings`。
为空或不可用时，课程知识库会显式使用 `local-hash-1536` 本地 fallback。

`MODEL_SETTINGS_ENCRYPTION_KEY` 必须使用 Fernet key。
生产环境必须替换为不可公开的强随机值；没有该值时，后端拒绝保存用户 API Key。

比赛演示建议优先配置讯飞星火 Spark：

```text
SYSTEM_MODEL_BASE_URL=https://spark-api-open.xf-yun.com/v1
SYSTEM_CHAT_MODEL=lite
```

讯飞原生 Embeddingp/Embeddingq 不在当前部署范围内。
真实密钥只能放在 `.env` 或用户加密配置中，不能写入仓库。

## 4. 启动最小服务

校验 Compose 配置：

```powershell
docker compose config
```

构建并启动：

```powershell
docker compose up --build -d
```

Compose 构建上下文会排除本地依赖和运行产物，包括 `node_modules`、`dist`、`.vite`、`.vite-temp`、`build`、`output`、缓存目录和日志文件。前端镜像必须在容器内重新安装依赖并完成生产构建，不能复用本机 `frontend/node_modules`。

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

本地开发只启动 PostgreSQL 和 Redis 时，可以使用本地虚拟环境执行：

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic upgrade head
```

完整 Docker 栈启动时，backend 容器会先执行 `python -m alembic upgrade head`，再启动 Uvicorn，确保已有本地 Docker 数据卷也能自动补齐最新迁移。需要排障或确认版本时，也可以直接在后端容器中执行。后端镜像已复制 `alembic.ini`，容器工作目录为 `/app`：

```powershell
docker compose exec -T backend python -m alembic upgrade head
docker compose exec -T backend python -m alembic current
```

当前首条迁移会执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

导入内置课程包：

```powershell
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
```

完整 Docker 栈中可以改用：

```powershell
docker compose exec -T backend python -m backend.app.cli seed-ai-intro
```

## 7. 当前验收标准

当前基础部署验收标准：

1. `docker compose config` 通过。
2. `postgres` 服务健康。
3. `redis` 服务健康。
4. `backend` 服务健康。
5. 浏览器或命令行访问 `/api/health` 返回预期 JSON。
6. 本地或后端容器内 `alembic upgrade head` 能完成 pgvector 扩展迁移。
7. 本地或后端容器内 `alembic upgrade head` 能创建第一批核心业务表和学习闭环基础表。
8. `python -m backend.app.cli seed-ai-intro` 能导入人工智能导论课程包。
9. 重复执行导入命令不会创建重复课程。
10. `frontend` 可执行 `pnpm lint`、`pnpm test` 和 `pnpm build`。
11. `frontend` 静态服务和 `nginx` 统一入口能通过 Compose 配置校验。
12. 停止服务后本地 Git 状态不出现运行产物。
13. 注册、登录、读取当前用户、退出登录和未登录受保护路由跳转可在浏览器中走通。
14. 登录后的 `/app` 首页通过 `/api/v1/dashboard/summary` 读取当前用户最近课程、主页历史、资料库摘要和空状态。
15. 登录后的 `/app` 上传资料会写入当前用户个人资料库，`/app/library` 通过 `/api/v1/materials` 读取真实资料列表。
16. 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料可以通过 `/api/v1/courses/from-materials` 生成当前用户自己的课程结构，成功后前端进入 `/app/courses/{course_id}` 并读取真实标题和知识点；旧版 DOC/PPT、图片和扫描件不伪装解析。
17. `/app/settings` 可以读取模型配置摘要和多配置列表，保存个人 OpenAI-compatible 配置，设为默认、删除并测试连接；前端不显示明文 Key。
18. 课程空间命中资料引用且模型配置可用时，可以通过 `/api/v1/tutor/sessions/{session_id}/messages` 或流式接口保存真实模型回答和引用；模型未配置时显示明确提示。
19. Phase 14 后，课程空间命中资料问题时引用区应显示外部向量混合检索或关键词 fallback；`local-hash-1536` 不作为课程语义命中，刷新后消息、引用和状态仍可恢复。
20. Phase 6.5 后，课程空间默认进入问答模式，知识点入口和引用可进入学习模式，默认首屏不常驻知识画布、资源区、证据层、横向知识点条或主区重复历史。

当前已验证记录按阶段存放在 [TEST_PLAN.md](TEST_PLAN.md)。

部署层重点只保留以下口径：

- `docker compose config` 必须通过。
- `backend`、`export-worker`、`postgres`、`redis`、`frontend`、`nginx` 服务必须可解析。
- 数据库必须能 `alembic upgrade head`。
- 前端必须能 `pnpm lint`、`pnpm test`、`pnpm build`。
- 真实用户链路需要通过浏览器验收。

浏览器验收优先使用 `agent-browser`。
Codex 内置浏览器用于补充可见确认、用户直接观看或 agent-browser 不可用时兜底。

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

当前前端已接入真实认证和主要学习数据：

- `/app` 通过 `/dashboard/summary` 读取最近课程、主页历史、资料库摘要和空状态。
- 主页消息发送会写入 `/tutor/sessions`。
- 主页上传和 `/app/library` 会调用 `/materials`。
- 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料可通过 `/courses/from-materials` 生成课程。
- 课程空间问题会持久化真实引用，并在默认模型可用时生成流式 RAG 回答。
- Phase 14 后，外部 embedding 可用时课程检索使用 pgvector SQL cosine 候选；本地或 Provider 失败显示关键词 fallback，不把 hash 标记为语义命中。
- Phase 6.5 后课程空间默认问答模式和学习模式都在同一路由内完成，不新增部署入口。
- `/app/settings` 可管理多套用户模型配置。
- `/app/profile`、`/app/studio`、`/app/path`、`/app/practice` 和 `/app/reports` 已接入真实画像、资源、路径、练习、报告和 Markdown/PDF/DOCX 异步导出接口。

本地开发时 Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。
如果后端端口变化，可以设置 `VITE_API_PROXY_TARGET`。

前端不应再用静态假资源、假画像、假练习或假报告填充真实数据缺口。模型未配置、资料不足或接口失败时，应展示真实空状态、低依据提示或局部错误。

## 9. 隔离 Docker E2E

Phase 14 提供独立验收脚本：

```powershell
.\scripts\test_e2e.ps1
```

脚本使用 Compose project `edunova-e2e`、独立端口和临时卷，显式用安全占位配置覆盖真实模型和联网 Key。它会从空库升级到 Alembic head，运行 Playwright 学习闭环，并在 `finally` 中执行 `down -v --remove-orphans`。默认入口为 `http://127.0.0.1:18080`，不会操作正式 `edunova` Compose 数据卷。

## 10. 后续部署计划

后续阶段将补充：

- 扩展 E2E 失败分支和更细粒度部署验收截图。
- 公网部署、TLS、反向代理和生产环境变量建议。
- 对象存储、日志轮转、备份恢复和监控建议。
- OCR、旧版 Office 解析、扫描件解析和生产级 worker 监控接入后的部署说明。
