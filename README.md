# EduNova

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

## 当前阶段

当前处于前期基础建设阶段。核心原则是先完成需求、架构、API、数据库、测试和项目管理基线，再进入大规模功能开发。

## 文档入口

| 文档 | 说明 |
| --- | --- |
| [赛题原文](docs/软件杯A3赛题.txt) | A3 赛题要求 |
| [仓库规则](AGENTS.md) | 编码、文档同步、Git、密钥和完成定义 |
| [产品设计](docs/superpowers/specs/2026-07-01-edunova-product-design.md) | EduNova 做什么 |
| [前端与交互设计基线](docs/UI_UX_DESIGN.md) | Phase 3 前端设计方向、页面结构和验收标准 |
| [前端路由与入口体验设计](docs/FRONTEND_ROUTING_DESIGN.md) | 登录、注册、Demo、首次进入和路由保护 |
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
- Demo Mode。
- Docker Compose 部署。

## 编码规则

- 所有文本文件使用 UTF-8 无 BOM。
- 禁止 UTF-16、GBK。
- 中文直接写入，不使用 `\uXXXX`。
- 不提交真实 `.env`、API Key、上传文件和缓存。

## 开发状态

当前 Phase 2 数据与课程基础建设已完成到内置人工智能导论课程包。FastAPI 最小应用、`/api/health` 健康检查、pytest 测试、编码检查、Docker Compose 草案、SQLAlchemy 数据库入口、Alembic 迁移基线、pgvector 扩展迁移、第一批核心业务表和人工智能导论内置课程包已经实现。

Phase 3 进入前端前，已先补充 [前端与交互设计基线](docs/UI_UX_DESIGN.md) 和 [前端路由与入口体验设计](docs/FRONTEND_ROUTING_DESIGN.md)：EduNova 正式前端不采用固定左侧后台菜单和卡片堆，而采用“顶部轻导航 + 中央学习画布 + 底部 AI 命令栏 + Studio 输出区 + 可滑出证据层”的 AI 学习空间结构；登录、注册、Demo 体验、首次进入引导和路由保护也已经作为 Phase 3A 基线锁定。前端和 AI/RAG 真实能力仍属于后续实现阶段。

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

校验配置：

```powershell
docker compose config
```

启动并构建：

```powershell
docker compose up --build -d postgres redis backend
```

停止：

```powershell
docker compose down
```

当前已验证三项服务 health 都能达到 `healthy`，且 `http://127.0.0.1:8000/api/health` 返回：

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

导入内置课程包：

```powershell
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
```

当前内置课程包包含 12 个知识点和 24 个基础资料切片，覆盖搜索、知识表示、机器学习、神经网络、自然语言处理、计算机视觉、多智能体和 AI 伦理安全。
