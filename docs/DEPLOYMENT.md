# EduNova 部署指南

推荐使用 Docker Compose 运行 EduNova。默认入口为 `http://127.0.0.1:8080`。

## 1. 前置条件

- Docker Desktop 或 Docker Engine；
- Docker Compose v2；
- 建议至少 8 GB 可用内存；
- 首次构建时可访问镜像、Python、Node 和模型依赖源。

## 2. 快速启动

Windows 可以依次运行：

```text
01_Check_Environment.bat
02_Start_EduNova.bat
```

手动启动：

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

首次启动前必须修改 `.env` 中的数据库密码、JWT 密钥和模型配置加密密钥。需要 AI 功能时，再配置相应 Provider。

## 3. 服务

| 服务 | 默认实现 | 用途 |
| --- | --- | --- |
| `postgres` | `pgvector/pgvector:pg16` | 关系数据和向量检索 |
| `redis` | `redis:7.2-alpine` | RQ 队列和短期运行状态 |
| `backend` | FastAPI | HTTP API、SSE 和领域服务 |
| `ai-worker` | RQ Worker | 资料解析与 AI 工作流 |
| `export-worker` | RQ Worker | 文档、课件和报告导出 |
| `code-verifier` | Pyodide 服务 | 隔离执行受支持的 Python 代码 |
| `frontend` | React 静态站点 | 浏览器界面 |
| `nginx` | Nginx | 统一入口与反向代理 |

生产部署只需公开 Nginx 端口。PostgreSQL、Redis、Backend、Worker 和代码验证服务应留在内部网络。

## 4. 必填配置

至少设置：

```text
POSTGRES_PASSWORD=<strong-password>
JWT_SECRET=<random-secret>
MODEL_SETTINGS_ENCRYPTION_KEY=<fernet-compatible-key>
```

`.env.example` 列出了全部配置，主要分为：

- 服务端口和运行环境；
- 数据库、Redis 和队列；
- Chat、Generation、Embedding、Rerank、Vision、Speech Provider；
- 模型超时、重试、并发和审计保留；
- 上传、文档解析和对象存储；
- ClamAV、OpenTelemetry 和日志。

不要把生产 `.env` 写入镜像、源码包或 Git。

## 5. 存储

开发环境默认使用本地卷：

- PostgreSQL 数据；
- Redis 数据；
- 上传资料与聊天附件；
- 导出文件。

公开部署可以设置 `STORAGE_BACKEND=s3`，并配置 S3-compatible endpoint、bucket、region 和凭据。应用数据库只保存逻辑键，不保存宿主机绝对路径。

## 6. 文档解析与文件安全

TXT 和 Markdown 使用轻量解析；PDF、DOCX 和 PPTX 可由 Docling 提取结构。扫描件、图片和旧版 Office 文件不会被标记为已完成深度解析。

公开上传入口建议启用：

- MIME 与扩展名一致性检查；
- 文件大小和解压限制；
- `CLAMAV_ENABLED=true` 的恶意文件扫描；
- 上传目录与应用代码分离；
- 对象存储最小权限。

## 7. 更新

更新前备份数据库和文件存储，然后执行：

```powershell
git pull --ff-only
docker compose build backend ai-worker export-worker frontend
docker compose run --rm backend python -m alembic upgrade head
docker compose up -d
docker compose ps
```

Backend 与 AI Worker 应使用同一代码版本。迁移完成后再滚动更新前端和 Nginx。

## 8. 健康检查

```powershell
docker compose config --quiet
docker compose ps
Invoke-RestMethod http://127.0.0.1:8080/api/health
```

预期健康响应：

```json
{"status":"ok","service":"edunova-api"}
```

## 9. 停止与重置

保留数据停止：

```powershell
docker compose down
```

删除本机 Compose 数据卷：

```powershell
docker compose down -v
```

第二条命令会不可恢复地删除数据库、队列和文件卷，只应在明确需要重置本地环境时执行。

## 10. 生产加固

- 使用 HTTPS，并限制允许的域名和跨域来源；
- 关闭 `APP_DEBUG`；
- 使用高强度独立密钥并定期轮换；
- 不公开 PostgreSQL、Redis、Backend 或代码验证端口；
- 为数据库、对象存储和密钥建立独立备份；
- 配置日志保留和敏感信息脱敏；
- 启用依赖告警、密钥扫描和镜像漏洞检查；
- 在真实浏览器中验证登录、上传、建课、辅导和任务恢复。

## 11. 发布检查

```powershell
.\scripts\verify_encoding.ps1
.\scripts\test.ps1
.\scripts\supply_chain.ps1
docker compose config --quiet
git diff --check
```

涉及 Provider 的质量和性能结论必须使用当前环境的新样本；未运行的检查应明确标记为未验证。
