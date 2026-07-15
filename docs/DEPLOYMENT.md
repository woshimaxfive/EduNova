# EduNova 部署说明

日期：2026-07-14

## 1. 当前部署范围

本文档记录 EduNova 的本地开发、Docker Compose 和部署准备方式。

当前部署范围覆盖十条生产 Graph、AI 任务运行时和动态检索：

- 工程骨架和 Docker Compose。
- 数据库迁移和内置课程包导入。
- 真实认证、首页、资料库、PDF/DOCX/PPTX 解析、规则建课、课程 RAG 和课程会话。
- 三能力模型配置、Spark X2-Flash、动态 Embedding、可选 Rerank、课程流式回答和课程空间双模式前端。
- 学习画像、课程学习状态、弱点复习队列和状态流转。
- Agent trace 查询和资源生成 trace。
- 六类 v3 证据型课程资源、并行 Worker、完整 artifact 质量审核、Markmap/Mermaid/Pyodide 和 PPTX 导出。
- 内部 `code-verifier` 使用 Pyodide 对生成的 Python 代码执行策略与预期输出验证；验证失败或服务不可用时不保存代码资源。
- 前端镜像会把 `pyodide.mjs` 与配套运行时复制到版本化目录 `/pyodide/0.29.2/`，Web Worker 直接导入自托管 loader；版本目录用于隔离 immutable 浏览器缓存。Nginx 必须保留 `.js`、`.mjs`、`.wasm`、`.json` 的正确 MIME，并按 Pyodide 官方分发兼容方式以 `application/wasm` 提供标准库 zip，同时返回 CORS、CORP 与 `nosniff` 安全头。
- 持续学习路径、规则掌握度图、练习评估、学习报告、资料对比和 Markdown/PDF/DOCX 学习档案导出。
- 主页联网搜索、深度回答指令、浏览器语音输入/朗读和 `home_tutor` trace。
- 交付基线文档、开源说明、MIT 许可证和验收证据索引。
- 前端本地开发、生产构建和 Nginx 统一入口草案。

- FastAPI backend。
- PostgreSQL + pgvector。
- Redis。
- RQ export worker。
- RQ AI worker。
- 仅 Docker 内部可访问的 code-verifier。
- React 前端静态服务。
- Nginx 统一入口。
- Nginx 使用 Docker 内置 DNS 动态解析前端与后端容器地址，服务重建后无需手动重启网关，也不会继续访问旧容器地址。
- Alembic 迁移。
- pgvector 扩展初始化。
- 用户、课程、选课、课程资料、个人资料库、课程资料关联、知识点、知识切片、画像、学习路径、生成资源、Agent 轨迹、练习、报告、对话和模型设置表。
- 数据结构与算法内置课程包同步命令。
- 注册、登录、读取当前用户和退出登录接口。
- 受保护学习空间首页总览接口 `/api/v1/dashboard/summary`。
- 受保护主页会话接口 `/api/v1/tutor/sessions`。
- 受保护资料库接口 `/api/v1/materials/upload`、`/api/v1/materials`、`/api/v1/materials/{material_id}`、`/api/v1/materials/{material_id}/progress` 和 `/api/v1/courses/{course_id}/materials`。
- 受保护课程接口 `/api/v1/courses/from-materials`、`/api/v1/courses`、`/api/v1/courses/{course_id}`、`/api/v1/courses/{course_id}/overview`、`/api/v1/courses/{course_id}/knowledge-points`、`/api/v1/courses/{course_id}/learning-state` 和 `/api/v1/courses/{course_id}/mastery-map`。
- 受保护 RAG 检索接口 `/api/v1/rag/search`，支持关键词、动态向量、RRF、可选重排序和关键词 fallback 状态。
- 受保护模型设置接口 `/api/v1/settings/model`、`/api/v1/settings/model/test` 和 `/api/v1/settings/model/configs` 系列接口。
- 受保护画像、Agent trace、资源、学习路径、练习、报告、资料对比、Markdown 同步导出和异步导出任务接口。
- React + TypeScript + Vite 前端本地开发服务器。
- 前端 lint、Vitest 和生产构建命令。
- 前端 API 合同模块，默认请求基础路径 `/api/v1`。
- 学生端核心页面，覆盖首页、资料库、课程空间（含 AI 辅导）、资源工坊、学习画像、练习、报告、学习路径和设置。

以下能力还未接入当前部署：

- OCR、旧版 Office、扫描件解析和文本之外的多模态向量检索。

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

`WEB_SEARCH_API_KEY` 为空时，星火/官方 OpenAI 的原生搜索仍可按 Provider 能力工作；DeepSeek 与普通兼容接口无法执行外部搜索并返回明确 warning，不生成假来源。原生搜索没有可验证 URL 时仍需要 `WEB_SEARCH_API_KEY` 才能回退。Docker Compose 中 backend 和 `export-worker` 共享导出卷，确保 worker 生成的学习档案可由下载接口读取；数据库迁移由 backend 启动命令执行，AI Worker 同时消费资源任务与跨会话记忆索引/回填任务。

Phase 25 新增迁移 `20260715_0024`。部署升级必须先执行 Alembic head，再滚动 backend 和 AI Worker；旧会话无需停机批量迁移，用户开启记忆时由幂等 RQ 回填任务渐进建立派生索引。关闭记忆或清除索引无需对象存储操作。

生成代码验证变量：

```text
CODE_VERIFIER_URL=http://code-verifier:8090
CODE_VERIFIER_TIMEOUT_SECONDS=8
```

本地不使用 Docker 时可以将 `CODE_VERIFIER_URL` 留空；此时代码资源明确失败，不能退回为未经运行的代码。Compose 中该服务不映射宿主机端口，只允许 backend 和 `ai-worker` 通过内部 `verification_net` 调用。

模型 Provider 相关变量：

```text
SYSTEM_MODEL_PROVIDER=openai_compatible
SYSTEM_MODEL_BASE_URL=https://api.example.com/v1
SYSTEM_MODEL_API_KEY=replace-with-your-own-key
SYSTEM_CHAT_MODEL=example-chat-model
SYSTEM_EMBEDDING_PROVIDER=openai_compatible
SYSTEM_EMBEDDING_BASE_URL=https://embedding.example.com/v1
SYSTEM_EMBEDDING_API_KEY=replace-with-your-embedding-key
SYSTEM_EMBEDDING_APP_ID=
SYSTEM_EMBEDDING_API_SECRET=
SYSTEM_EMBEDDING_MODEL=example-embedding-model
SYSTEM_EMBEDDING_DIMENSION=
SYSTEM_RERANK_PROVIDER=
SYSTEM_RERANK_BASE_URL=
SYSTEM_RERANK_API_KEY=
SYSTEM_RERANK_MODEL=
SYSTEM_RERANK_WORKSPACE_ID=
MODEL_SETTINGS_ENCRYPTION_KEY=replace-with-fernet-key
MODEL_REQUEST_TIMEOUT_SECONDS=20
```

`SYSTEM_MODEL_*`、`SYSTEM_EMBEDDING_*` 和 `SYSTEM_RERANK_*` 分别是服务器回答、向量和重排序兜底配置。讯飞向量额外需要 APPID 与 APISecret；三类用途互相独立。

Docker Compose 会把仓库根目录的 `.env` 作为 backend 容器的可选运行时环境文件读取，用于注入 `SYSTEM_MODEL_*`、`MODEL_SETTINGS_ENCRYPTION_KEY` 等服务器配置。`.env` 已被 `.gitignore` 忽略，不能提交真实密钥。为了避免把密钥展开到终端日志，统一验证脚本只运行 `docker compose config --quiet`。

个人模型配置通过 `/settings/model/configs` 保存到 `model_settings`：

- 主页、课程回答和生成型 Graph 优先使用当前用户回答默认配置。
- 资料与课程 RAG 的 Embedding 优先使用当前用户向量默认配置。
- 每套个人配置都能为回答、向量和重排序分别保存 Provider、地址、凭证和模型；同一套方案可组合不同服务商。
- 三类默认可指向同一套或不同套配置；某一用途没有个人默认时，只回退该用途的服务器配置。
- 用户 API Key 使用 Fernet 加密保存。
- 接口只返回脱敏 Key，不返回明文。

`SYSTEM_EMBEDDING_MODEL` 在没有个人向量默认时使用。Provider 为 `xfyun_embedding` 时走讯飞原生签名协议；其他 Provider 走 OpenAI-compatible `/embeddings`。为空或不可用时显式退回关键词检索。

`MODEL_SETTINGS_ENCRYPTION_KEY` 必须使用 Fernet key。
生产环境必须替换为不可公开的强随机值；没有该值时，后端拒绝保存用户 API Key。

比赛演示建议优先配置讯飞星火 Spark：

```text
SYSTEM_MODEL_BASE_URL=https://spark-api-open.xf-yun.com/agent/v1/
SYSTEM_CHAT_MODEL=spark-x
```

讯飞 LLM Embedding 可通过独立服务器向量配置或用户设置页启用；免费额度与授权状态以讯飞控制台为准。
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

Compose 使用四个固定命名卷：`postgres_data` 保存数据库，`redis_data` 保存 RQ 队列与运行时状态，`export_data` 保存导出文件，`material_data` 让 backend 与 `ai-worker` 共享用户原文件。固定卷可以避免容器重建时不断产生长哈希匿名卷。普通 `docker compose down` 会保留数据；只有明确需要从零重置本地环境时才执行 `docker compose down -v`，该命令会不可恢复地删除四个卷。

## 5. 服务说明

| 服务 | 镜像或构建 | 端口 | 说明 |
| --- | --- | --- | --- |
| `postgres` | `pgvector/pgvector:pg16` | `5432` | PostgreSQL + pgvector |
| `redis` | `redis:7-alpine` | `6379` | 缓存、进度和 RQ 队列，使用固定 `redis_data` 卷 |
| `backend` | `docker/backend.Dockerfile` | `8000` | FastAPI 后端 |
| `ai-worker` | `docker/backend.Dockerfile` | `material_data` | 资料解析、建课、资源和向量重建 RQ Worker |
| `export-worker` | `docker/backend.Dockerfile` | 无 | 学习档案与 PPTX 导出 RQ Worker |
| `code-verifier` | `docker/code-verifier.Dockerfile` | 仅内部 `8090` | 生成 Python 代码的隔离验证服务 |
| `frontend` | `docker/frontend.Dockerfile` | 内部 `8080` | Vite 生产构建后的静态前端，由非 root Nginx 托管，只供统一入口访问 |
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

同步内置课程包并清理旧内置课：

```powershell
.\.venv\Scripts\python -m backend.app.cli sync-builtin-courses
```

完整 Docker 栈中可以改用：

```powershell
docker compose exec -T backend python -m backend.app.cli sync-builtin-courses
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
8. `python -m backend.app.cli sync-builtin-courses` 能安装数据结构与算法课程，并按内部 slug 清理旧内置课。
9. 重复执行同步命令不会创建重复课程，也不会删除用户自行创建的同名课程。
10. `frontend` 可执行 `pnpm lint`、`pnpm test` 和 `pnpm build`。
11. `frontend` 静态服务和 `nginx` 统一入口能通过 Compose 配置校验。
12. 停止服务后本地 Git 状态不出现运行产物。
13. 注册、登录、读取当前用户、退出登录和未登录受保护路由跳转可在浏览器中走通。
14. 登录后的 `/app` 首页通过 `/api/v1/dashboard/summary` 读取当前用户最近课程、主页历史、资料库摘要和空状态。
15. 登录后的 `/app` 上传资料会写入当前用户个人资料库，`/app/library` 通过 `/api/v1/materials` 读取真实资料列表。
16. 已解析 TXT/Markdown/PDF/DOCX/PPTX 资料可以通过 `/api/v1/courses/from-materials` 生成当前用户自己的课程结构，成功后前端进入 `/app/courses/{course_id}` 并读取真实标题和知识点；旧版 DOC/PPT、图片和扫描件不伪装解析。
17. `/app/settings` 可以读取模型配置摘要和多配置列表，保存个人 OpenAI-compatible 配置，设为默认、删除并测试连接；前端不显示明文 Key。
18. 课程空间命中资料引用且模型配置可用时，可以通过 `/api/v1/tutor/sessions/{session_id}/messages` 或流式接口保存真实模型回答和引用；模型未配置时显示明确提示。
19. 课程空间命中资料问题时引用区应显示关键词、向量、混合与重排序状态；外部能力不可用时显示关键词 fallback，刷新后消息、引用和状态仍可恢复。
20. Phase 6.5 后，课程空间默认进入问答模式，知识点入口和引用可进入学习模式，默认首屏不常驻知识画布、资源区、证据层、横向知识点条或主区重复历史。

当前已验证记录按阶段存放在 [TEST_PLAN.md](TEST_PLAN.md)。

部署层重点只保留以下口径：

- `docker compose config` 必须通过。
- `backend`、`ai-worker`、`export-worker`、`code-verifier`、`postgres`、`redis`、`frontend`、`nginx` 服务必须可解析。
- `code-verifier` 必须无宿主机端口、使用内部网络、非 root、只读文件系统、临时目录、能力全移除和进程/内存/CPU 限制。
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
- 日志轮转、备份恢复和生产监控建议。
- OCR、旧版 Office 解析、扫描件解析和生产级 worker 监控接入后的部署说明。

## 11. Phase 22 基础设施配置

- AI Worker 镜像固定安装 `docling-slim` 并预装模型制品；运行时关闭远程插件和 OCR。无法提供离线制品时可设置 `EDUNOVA_DOCUMENT_PARSER=legacy` 显式回滚，不能静默双解析。
- `STORAGE_BACKEND=local` 是本地默认；公开部署可配置 S3-compatible endpoint、bucket、region 和独立访问凭据。数据库不需要随存储切换迁移。
- ClamAV 本地默认关闭。公开部署使用 `docker compose --profile security up -d` 启动固定版本 sidecar，并设置 `CLAMAV_ENABLED=true`；启用后病毒或扫描服务不可用都会拒绝入库。
- OTLP 未配置时 OpenTelemetry 为 no-op；配置 Collector endpoint 后才导出通用运行 span，且不发送业务正文或认证信息。
- Promptfoo 默认离线，Ragas 联网评测需显式设置 `EDUNOVA_EVAL_ALLOW_NETWORK=1`；生产容器不需要安装网络评测依赖。
- Docling 镜像验收可运行 `docker compose run --rm ai-worker python -m backend.evals.docling_benchmark`；本地教材通过只读挂载显式提供，输出只保留脱敏聚合指标。
- backend、export-worker 与 ai-worker 使用固定 UID/GID 10001 的 `edunova` 用户；前端静态服务使用 `nginx-unprivileged` 的 UID 101。命名卷初始化时继承镜像内可写目录权限，升级既有外部卷前应先核对属主。

大陆网络首次构建较慢时，可只在构建阶段配置镜像源，不改变运行时 Provider 或模型请求地址：

```powershell
$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
$env:HF_ENDPOINT = "https://huggingface.co"
$env:NPM_REGISTRY = "https://registry.npmmirror.com"
$env:DEBIAN_MIRROR = "https://mirrors.tuna.tsinghua.edu.cn/debian"
$env:DEBIAN_SECURITY_MIRROR = "https://mirrors.tuna.tsinghua.edu.cn/debian-security"
$env:TORCH_INDEX_URL = "https://mirrors.nju.edu.cn/pytorch/whl/cpu"
docker compose build
```

这些配置均为可选 Build Args；不设置时回到 Debian、PyPI、Hugging Face 和 npm 官方源。发布构建需要同时保留固定版本、依赖审计和许可证门禁，不能因为使用镜像源而跳过供应链检查。

AI Worker 默认从 PyTorch 官方 CPU index 安装固定 `torch`/`torchvision` CPU wheel；网络受限时可显式切换到已验证的高校镜像。不要改回 PyPI 默认 Linux wheel，否则会额外引入 CUDA、cuDNN、NCCL 等当前不使用的 GPU 运行库，并显著放大镜像。

## 12. Phase 26 部署影响

Phase 26 只新增 backend JSON 路由和 frontend 静态代码，不新增环境变量、镜像依赖、Worker 队列、数据卷或 Alembic 迁移。滚动更新 backend 与 frontend/nginx 即可；旧客户端和 `DashboardSummary.empty_state.action_label` 保持兼容。发布后可用已登录账号请求 `/api/v1/learning/next-action` 验证用户隔离与响应 Schema。

## 13. Phase 28 部署与性能注意事项

Phase 28 不新增服务、端口、环境变量或数据库迁移。OpenAPI 检查在临时目录生成并比较，供应链门禁独立生成直接依赖来源、版本、许可证和用途清单。

真实验收发现同步路径规划可能需要 53–62 秒，并在默认 nginx 请求窗口出现过一次 504。发布环境不得简单提高代理超时后宣称问题消失；在路径规划迁移到既有 AIJob/RQ 可恢复异步链路前，应明确前端等待/失败提示、代理超时和重试的幂等边界。SSE、AIJob、RAG 和三类资源批次的 Phase 28 指标单独达标，不能用来替代路径规划长尾风险。

## 14. Phase 29 部署影响

Phase 29 不新增服务、端口、环境变量、依赖或数据库迁移。`ai-worker` 必须与 backend 同版本部署以识别 `path_planning`；滚动更新时先发布兼容 Worker/backend，再发布前端。路径请求进入既有 `edunova_ai` 队列，nginx 不再维持 60 秒同步连接。国内内容策略只改变 Prompt、来源排序与前端标签，不改变 Provider 地址；B站成功后不会再消耗 YouTube 搜索调用。

## 15. Phase 31 大型教材部署影响

Phase 31 不新增服务、端口、依赖或环境变量。`ai-worker` 与 backend 必须同版本发布，以同时具备源页数质量门禁和大小感知 Docling 时限。小文件仍保持 120 秒；大于 10 MiB 的 PDF 按文件大小增加解析窗口，最终不超过 AIJob 时限减 60 秒。该策略只延长有持续真实心跳的大教材解析，不放宽无心跳卡死、取消或 Worker 失联判定。

生产部署应为 AI Worker 预留足够 CPU、内存和临时磁盘。437 页、约 24.4 MiB 文本层 PDF 的本机 Docker 实测解析约 11 分 45 秒，该值是单机样本而非 SLA；监控应区分 Docling 本地耗时与 Provider 外部耗时。教材文件、切片、Prompt 和模型原始响应不得进入通用 trace 或构建产物。
