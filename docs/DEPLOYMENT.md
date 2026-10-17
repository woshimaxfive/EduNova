# EduNova 部署指南

本指南适用于 Docker Compose 部署；Windows 桌面安装见[桌面分发说明](DESKTOP_DISTRIBUTION.md)。Docker 默认入口为 `http://127.0.0.1:8080`。

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

逐条执行，失败即停止；不要跳过模型准备。Windows 一键入口自动检查退出码。初始化生成数据库密码、JWT、配置加密密钥和 SearXNG 内部密钥，不附带主模型 API Key；主模型可在设置页或系统配置中填写。

首次准备下载向量与语音识别权重，并检查离线推理。Linux/macOS 需按[本地检索](LOCAL_EMBEDDING.md)和[本地语音](LOCAL_SPEECH.md)准备权重、设置下方安全项，再运行 Compose；仅执行 `up` 不足以完成安装。升级前备份数据库和 `.env`，迁移会清理退役的外部检索、搜索与语音配置。

已有 PostgreSQL 数据卷时，先初始化 `.env` 再同步角色密码，保留课程、用户及其他数据：

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

端口默认只绑定 `127.0.0.1`。生产环境只公开受保护的 Nginx 入口；数据库、Redis、Backend、Worker 和代码验证服务留在内部网络。

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

公开部署可设置 `STORAGE_BACKEND=s3`，配置 S3-compatible endpoint、bucket、region 和凭据。数据库保存逻辑键，不保存宿主机绝对路径。

## 6. 文档解析与文件安全

TXT/Markdown 使用轻量解析，PDF/DOCX/PPTX 可由 Docling 提取结构。扫描件、图片与旧版 Office 文件不标记为已完成深度解析。

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

Provider 质量与性能结论须有当前环境的新样本；未运行项标为未验证。

## 12. 模型与版本维护边界

示例聊天与生成模型为 `qwen3.8-flash`，个人配置可覆盖系统配置。图片理解复用主模型；本地向量、RRF、SearXNG 与语音无需额外 Key，搜索仍依赖网络及上游服务。修改 `.env.example` 不会更新已有 `.env`。

`python -m scripts.check_live_models` 使用合成输入检查系统聊天、生成与向量连接，会产生真实模型调用费用。输出不含密钥，默认保存在忽略目录 `output/release-readiness/`。

连接成功或少量演示不能证明教学质量、完整学习流程和并发性能。离线夹具的引用与分数不能作为新回答的证据；只有真实文本时，这两项仍未验证。发布检查分别记录离线质量、诊断耗时和完整真实验收，证据不足保留 `evidence_gap`。

资源生成与修订传入真实引用编号；敏感内容错误只记录规则名，不保存原始响应。

回退 Git 只恢复源码，不恢复 `.env`、依赖、镜像和数据库。分别用 `python -m alembic heads`、`python -m alembic current` 核对源码与目标数据库版本；已执行后续迁移时需另查兼容性。先备份、确认迁移策略，不得为运行旧代码删除数据卷。回归使用隔离 E2E 项目。

安装前端与评测工具时保留各自的 `pnpm-workspace.yaml` 和锁文件。用 `pnpm check:deps` 检查评测依赖兼容性；审计须包含开发依赖中的 Promptfoo，不能用 `--prod` 排除。SWC 安装脚本已禁用，当前评测无需编译自定义 TypeScript 插件。

### 记忆语义筛选

`CONVERSATION_MEMORY_SEMANTIC_SELECTION_ENABLED=true` 默认开启，已有显式 `false` 保持关闭，沿用原阈值检索（默认 0.72）。筛选使用现有对话模型，最多 5 条候选、每条 1600 字符；问题超过 4000 字符时沿用原检索，避免截断条件。每次至多增加一次结构化调用，超时 12 秒，仅尝试一次。

未配置、个人结构化能力测试未通过、调用失败、输出无效或返回未知 ID 时，均回退原阈值结果，不放行全部扩展候选；合法 none 才表示无匹配。歧义保留独立来源并要求澄清。

该服务级开关不替代个人隐私设置，变更后需重建或重启 backend 与相关 worker。有候选时可能增加 token 和等待时间，模型与问法仍需实际验证。审计操作为 `chat:memory_selection`、purpose 为 `memory_selection`，沿用既有用量展示；失败回退仅记无正文日志，缺失报价保持未知。

## 模型用量与记忆配置

默认记录服务商返回的 token，无需修改提示词或新增服务。OpenAI、DeepSeek 和 DashScope 的已知官方域名会请求流式用量；自定义服务默认不附加参数。确认支持后可在 `.env` 设置 `MODEL_STREAM_USAGE_ENABLED=true`，重启后端与 AI worker。未返回用量时显示未知，不重发请求。

首页遇到 `</final_answer>` 后不再显示正文，继续读取当前流的末尾用量帧。尾部文字不发到页面，异常或取消如实记录。每次读取前检查取消；已阻塞的同步读取仍受上游超时约束。不新增请求或补造用量。

`MODEL_USAGE_PRICING` 默认 `{}`，不估算费用。按精确键 `provider_source:配置ID或system:模型名` 配置每百万 token 价格。以下为合成示例，非实际报价：

```dotenv
MODEL_USAGE_PRICING={"user:123:example-model":{"currency":"CNY","uncached_input_tokens":"2","cache_read_tokens":"0.2","cache_write_tokens":"3","output_tokens":"8"}}
```

仅支持明确的 CNY/USD 报价；输入、缓存读写或输出计数不完整时不估算，不将未知补零。推理 token 已含在输出中，不重复计费。更换模型或中转地址后重查报价；估算不含搜索工具、税费、包月等非 token 费用，以供应商账单为准。用量可在设置页和轨迹 API 查看。

输入预算使用 `TUTOR_CONTEXT_WINDOW_TOKENS` 和 `TUTOR_OUTPUT_RESERVE_TOKENS`。超出时依次省略旧历史、记忆、外部搜索和多余课程片段，保留固定规则、当前问题与至少一段课程依据。这是保守文本估算，不替代模型 tokenizer 或计费数据。

记忆管理需迁移 `20260925_0039`：保留摘要与索引，增加用户确认的长期信息和无正文删除标记。`CONVERSATION_MEMORY_MIN_SIMILARITY` 默认 0.72，需按嵌入模型校准。暂停保留内容，恢复不自动回填；清除派生索引后，在设置页手动重建，由既有 AI worker 执行。存在长期信息、删除标记或隐私版本变更时拒绝降级，避免丢失删除保障；迁移前备份数据库。
