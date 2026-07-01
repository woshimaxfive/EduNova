# EduNova 部署说明

日期：2026-07-01

## 1. 当前部署范围

本文档记录 EduNova 的部署方式。当前 Phase 2B 已覆盖工程骨架和核心数据表迁移：

- FastAPI backend。
- PostgreSQL + pgvector。
- Redis。
- Alembic 迁移。
- pgvector 扩展初始化。
- 用户、课程、选课、资料、知识点和知识切片表。

以下能力还未接入当前部署：

- React 前端。
- Nginx。
- 内置课程导入。
- AI/RAG、多智能体、上传资料和学习业务。

这些能力会在后续阶段逐步加入，并同步更新本文档。

## 2. 前置条件

本地需要安装：

- Docker Desktop。
- Docker Compose。
- Git。

检查命令：

```powershell
docker --version
docker compose version
docker ps
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

## 7. 当前验收标准

Phase 2B 当前验收标准：

1. `docker compose config` 通过。
2. `postgres` 服务健康。
3. `redis` 服务健康。
4. `backend` 服务健康。
5. 浏览器或命令行访问 `/api/health` 返回预期 JSON。
6. `alembic upgrade head` 能完成 pgvector 扩展迁移。
7. `alembic upgrade head` 能创建第一批核心业务表。
8. 停止服务后本地 Git 状态不出现运行产物。

当前本机已验证以上 8 项，并验证第二条迁移可以 downgrade/upgrade 往返。

## 8. 后续部署计划

后续阶段将补充：

- 后端数据库连接检查。
- 内置人工智能导论课程数据导入。
- 前端构建和静态服务。
- Nginx 统一入口。
- Demo Mode 初始化命令。
- 生产部署建议。
