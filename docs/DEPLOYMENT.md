# EduNova 部署说明

日期：2026-07-01

## 1. 当前部署范围

本文档记录 EduNova 的部署方式。当前已覆盖工程骨架、核心数据表迁移、人工智能导论内置课程包导入命令和 Phase 3 前端本地开发/构建：

- FastAPI backend。
- PostgreSQL + pgvector。
- Redis。
- Alembic 迁移。
- pgvector 扩展初始化。
- 用户、课程、选课、资料、知识点和知识切片表。
- 人工智能导论内置课程包导入命令。
- React + TypeScript + Vite 前端本地开发服务器。
- 前端 lint、Vitest 和生产构建命令。
- 前端 API 合同模块，默认请求基础路径 `/api/v1`。
- Phase 3 学生端核心页面骨架，覆盖资料库、资源工坊、学习画像、AI 辅导、练习、报告和设置。

以下能力还未接入当前部署：

- Nginx。
- Docker 前端静态服务。
- AI/RAG、多智能体、上传资料和学习业务。

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

## 4. 启动最小服务

校验 Compose 配置：

```powershell
docker compose config
```

构建并启动：

```powershell
docker compose up --build -d postgres redis backend
```

查看服务：

```powershell
docker compose ps
```

健康检查：

```text
http://127.0.0.1:8000/api/health
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

如果本机端口已被占用，可以在 `.env` 中改为其他宿主机端口：

```text
POSTGRES_PORT=15432
REDIS_PORT=16379
BACKEND_PORT=18000
```

Compose 未固定 `container_name`，同机多个 checkout 可以通过不同项目名和端口并存。需要显式指定项目名时可使用：

```powershell
docker compose -p edunova-dev up --build -d postgres redis backend
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
7. `alembic upgrade head` 能创建第一批核心业务表。
8. `python -m backend.app.cli seed-ai-intro` 能导入人工智能导论课程包。
9. 重复执行导入命令不会创建重复课程。
10. `frontend` 可执行 `pnpm lint`、`pnpm test` 和 `pnpm build`。
11. 停止服务后本地 Git 状态不出现运行产物。

当前本机已验证后端与数据库基础验收项，并验证第二条迁移可以 downgrade/upgrade 往返。Phase 3 已验证前端 lint、Vitest 和 Vite build，覆盖 AI 对话主页、课程空间路由、学生端核心页面、学习空间路由、API 合同和上传建课状态模型；P3R3 对话主页已用本地浏览器检查桌面和移动宽度的 `/app` 首屏，无水平溢出，资料库浮层和生成课程浮层可打开且保持可读。P3.6 已用本地 Edge + Playwright 补充资料库、资源工坊、画像、辅导、练习、报告和设置在桌面与 390px 移动宽度下的可见性和无水平溢出检查。P3.8 已用 Edge + Playwright 检查分层导航：桌面顶部一级入口只保留学习空间、资料库和资源工坊，个人菜单可进入画像、报告和设置；390px 移动宽度无水平溢出；课程空间可见 AI 辅导、练习和报告行动入口。GPT 式主页壳和文件库式资料库已用 Edge + Playwright 检查：桌面端侧栏贴左边缘、可收起，侧栏个人资料/设置/退出可见，输入框宽度收窄，上传资料文件能进入本地演示资料库，资料默认未选中且点选后高亮，联网搜索可激活，Enter 发送后进入主页对话态并显示下方输入区；`/app/library` 的从资料生成课程浮层覆盖整个视口；390px 移动宽度无水平溢出。P3.9 已用 Edge + Playwright 复验登录页无共享演示学生按钮、注册页空白 starter mode、空白主页无内置课程和资料、资料库路由与课程空间路由复用贴边工作区侧栏、课程侧栏历史可切换当前线程，以及 390px 移动宽度无水平溢出。本轮又复验了资料库视觉和交互：普通路由侧栏显示主页全局历史，资料库去掉突兀硬白表格块，文档/图片筛选可用，上传资料进入列表，生成课程浮层内资料可选。P3.10 已完成界面文案减法，核心页面短标题、短说明和资源工坊短状态信号已通过测试与浏览器抽查；主页首屏解释句已移除，资料来源提示只在选择资料或开启联网后出现，并已在桌面和 390px 移动宽度下复验无水平溢出。P3.15 已用 Codex 内置浏览器复验：连续追问不重复新增历史，回答附加信息默认折叠且可展开/切换/收起，搜索历史浮层可过滤，资料库未选择资料时主按钮禁用，资料库到生成课程保持单一浮层，创建课程草案后关闭并反馈，资源工坊只保留一个生成资源按钮；390px 下 `/app` 和 `/app/library` 无水平溢出。P3.16 已用 Codex 内置浏览器复验：退出后登录页邮箱和密码为空且不显示 demo 邮箱；资源工坊五类资源为讲解、练习、思维导图、代码实操和 PPT 大纲；课程空间展开 Agent 过程后显示 PathAgent 且不显示 PlannerAgent；资料库图片资料显示“仅入库，暂不做 OCR”；390px 下 `/app/studio` 和 `/app/library` 无水平溢出。

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

当前前端使用本地预览会话和静态演示数据，不要求后端认证接口已经可用。前端业务接口合同默认指向 `/api/v1`，真实联调时需要后端按 `docs/API.md` 暴露对应路由。

## 9. 后续部署计划

后续阶段将补充：

- 后端数据库连接检查。
- Docker 前端构建和静态服务。
- Nginx 统一入口。
- 演示模式初始化命令。
- 生产部署建议。
