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

Windows 手动启动（只在 `.env` 不存在时复制，避免覆盖已有密钥）：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/initialize_env.ps1 -Path .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_postgres_password.ps1 -Path .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_local_runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_local_retrieval_env.ps1 -Path .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_local_search_env.ps1 -Path .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/migrate_local_speech_env.ps1 -Path .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

每条命令成功后再执行下一条；发生错误应停止，不要跳过模型准备。Windows 一键入口会自动检查各步骤退出码。初始化生成数据库密码、JWT、配置加密密钥和 SearXNG 内部密钥，不附带主模型 API Key。AI 功能可在设置页配置主模型，或由部署者配置系统主模型。

首次准备会下载本地向量及语音识别权重并执行离线推理检查。Linux/macOS 请按[本地检索](LOCAL_EMBEDDING.md)和[本地语音](LOCAL_SPEECH.md)准备权重，同时设置下面的安全项，再运行 Compose；不要仅执行 `up` 就认为已完成首次安装。旧部署先备份数据库和 `.env`，迁移脚本会清除已退役的外部检索、搜索和语音配置。

若升级前已创建 PostgreSQL 数据卷，先初始化 `.env`，再执行以下命令同步数据库角色密码。该操作不会删除课程、用户或其他数据库内容：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\initialize_env.ps1 -Path .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync_postgres_password.ps1 -Path .env
```

## 3. 服务

| 服务 | 默认实现 | 用途 |
| --- | --- | --- |
| `postgres` | `pgvector/pgvector:pg16` | 关系数据和向量检索 |
| `redis` | `redis:8.0-alpine` | RQ 队列和短期运行状态 |
| `backend` | FastAPI | HTTP API、SSE 和领域服务 |
| `ai-worker` | RQ Worker | 资料解析与 AI 工作流 |
| `export-worker` | RQ Worker | 文档、课件和报告导出 |
| `code-verifier` | Pyodide 服务 | 隔离执行受支持的 Python 代码 |
| `frontend` | React 静态站点 | 浏览器界面 |
| `nginx` | Nginx | 统一入口与反向代理 |
| `searxng` | SearXNG | 免 Key 联网搜索，仍访问外部上游 |
| `speech` | 本地 SenseVoiceSmall | 语音识别，模型权重只读挂载 |
| `clamav` | `clamav/clamav:1.4`（`security` profile） | 可选的恶意文件扫描 |

默认宿主机端口只绑定 `127.0.0.1`。生产部署只需通过受保护的入口公开 Nginx；PostgreSQL、Redis、Backend、Worker 和代码验证服务应留在内部网络。

## 4. 必填配置

至少设置：

```text
POSTGRES_PASSWORD=<strong-password>
JWT_SECRET=<random-secret>
MODEL_SETTINGS_ENCRYPTION_KEY=<fernet-compatible-key>
SEARXNG_SECRET=<random-secret>
```

`.env.example` 列出了全部配置，主要分为：

- 服务端口和运行环境；
- 数据库、Redis 和队列；
- 主模型对话/生成配置（图片能力跟随主模型），本地向量及语音运行参数；
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

## 12. 模型与版本维护边界

聊天和生成示例配置使用 `qwen3.8-flash`，个人主模型配置可覆盖系统配置。图片能力复用主模型，本地向量、RRF 排序、SearXNG 搜索及本地语音不要求额外服务 Key。仅修改 `.env.example` 不会改写部署环境的 `.env`。搜索免 Key 不等于离线，也不保证上游始终可用。

可执行 `python -m scripts.check_live_models` 以合成输入探测当前系统聊天、生成和向量连接。这会产生真实模型调用费用，输出不含密钥，结果默认保存在忽略目录 `output/release-readiness/`。连接成功不代表教学质量、完整学习闭环或性能验收通过。

离线夹具中的引用归属和服务端分数不作为新模型回答的证据。仅得到真实回答文本时，这两项保持未验证；发布检查区分离线质量、诊断耗时和完整真实验收，证据不足仍为 `evidence_gap`，不能因为探测成功宣布发布通过。

资源生成和修订均传入真实引用编号；敏感内容错误只记录规则名，不保存原始响应。模型连接成功、少量演示成功与系统性教学质量/性能评测是不同的验证层级。

回退 Git 只恢复受跟踪源码，不回退 `.env`、已安装依赖、镜像和数据库。用 `python -m alembic heads` 核对源码迁移头，用 `python -m alembic current` 核对目标数据库；已执行后续迁移的数据库不可直接认定兼容。先备份并确认迁移策略，禁止为启动旧代码直接删除数据卷。回归使用隔离 E2E 项目，不使用个人数据库。

前端和评测工具安装时保留各自的 `pnpm-workspace.yaml` 与锁文件。评测依赖兼容检查使用 `pnpm check:deps`；Promptfoo 位于开发依赖，审计不能使用 `--prod` 排除它。SWC 安装脚本明确禁用，当前评测入口不需要编译自定义 TypeScript 插件。
