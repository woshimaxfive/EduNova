# EduNova 开发指南

更新时间：2026-07-05

## 1. 开发原则

EduNova 采用学生端优先的迭代方式。每个阶段都必须同时满足：

- 代码或文档已经落盘。
- 相关测试和检查已运行。
- 文档与实现同步。
- 不提交真实密钥、JWT、用户资料和上传文件。
- 所有文本文件保持 UTF-8 无 BOM，中文不转义。
- 涉及 UI 或流程时使用 `agent-browser` 做真实浏览器验收。

## 2. 分支与提交

当前开发分支：

```powershell
feature/edunova-foundation
```

日常开始前：

```powershell
git status --short --branch
git pull --ff-only origin feature/edunova-foundation
```

提交前：

```powershell
git diff --check
git status --short --branch
```

提交粒度：

- 一个稳定阶段一个清晰 commit。
- 不把无关格式化、缓存、截图和运行产物混进功能提交。
- 不直接在 `main` 上开发。

## 3. 本地后端

创建环境：

```powershell
py -3.12 -m venv .venv
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

运行测试：

```powershell
.\.venv\Scripts\python -m pytest backend\tests
```

启动后端：

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get
```

## 4. 本地前端

安装依赖：

```powershell
cd frontend
pnpm install
```

开发服务器：

```powershell
pnpm dev
```

默认访问：

```text
http://127.0.0.1:5173
```

验证：

```powershell
pnpm lint
pnpm test
pnpm build
cd ..
```

Vite 本地开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 5. Docker 开发

校验：

```powershell
docker compose config --quiet
```

启动：

```powershell
docker compose up --build -d
```

迁移状态：

```powershell
docker compose exec -T backend python -m alembic current
```

统一入口：

```text
http://127.0.0.1:8080
http://127.0.0.1:8080/api/health
```

停止：

```powershell
docker compose down
```

## 6. 统一验证

日常阶段门禁：

```powershell
.\scripts\verify_encoding.ps1
.\scripts\test.ps1
```

`scripts/test.ps1` 会覆盖编码检查、后端测试、前端 lint、前端测试、Vite build、Alembic head 和 Docker Compose 配置校验。

## 7. 浏览器验收

涉及前端 UI、路由、交互、响应式或用户流程时必须补真实浏览器验收。

默认工具：

```powershell
agent-browser
```

Phase 12.2 的最低验收宽度：

- 桌面宽度。
- `390px` 移动宽度。

验收必须优先使用真实数据链路，例如注册时选择“带一个示例课程开始”，而不是把前端假数据当作完成证据。

## 8. 文档同步

发生以下变化必须同步文档：

- API 路径、请求、响应和错误码。
- 数据库表、字段和关系。
- 功能范围和里程碑状态。
- 测试方式和验收标准。
- 部署端口、环境变量和启动流程。
- 安全、隐私和开源边界。

常用同步文件：

- `README.md`
- `docs/STATUS.md`
- `docs/PROJECT_BOARD.md`
- `docs/API.md`
- `docs/DATABASE_DESIGN.md`
- `docs/FRONTEND_ROUTING_DESIGN.md`
- `docs/TEST_PLAN.md`
- `docs/DEPLOYMENT.md`

## 9. 安全边界

禁止提交：

- `.env`
- 真实 API Key
- JWT
- 用户上传资料
- 用户隐私原文
- 系统提示词和完整模型输入
- 运行缓存、日志和构建产物

如需演示，使用注册页示例课程模式或临时本地测试账号。
