# EduNova 测试报告

更新时间：2026-07-10

## 1. 报告定位

本文档汇总 EduNova 当前交付基线的验证方式和结果索引。详细测试范围仍以 [TEST_PLAN.md](TEST_PLAN.md) 为准，阶段状态以 [STATUS.md](STATUS.md) 为准。

Phase 12.2 的验收记录见：

```text
docs/evidence/PHASE_12_2_ACCEPTANCE.md
```

## 2. 自动化测试基线

统一验证命令：

```powershell
.\scripts\verify_encoding.ps1
.\scripts\test.ps1
.\scripts\test_e2e.ps1
```

`scripts/test.ps1` 覆盖：

- UTF-8 无 BOM 编码检查。
- 后端 pytest。
- 前端 ESLint。
- 前端 Vitest。
- Vite 生产构建。
- Alembic head 检查。
- Docker Compose 配置校验。

Phase 14 当前全量结果：

- 后端 pytest：220 项通过。
- 前端 Vitest：19 个文件、166 项通过。
- ESLint、ruff、TypeScript/Vite build：通过。
- 隔离 Docker Playwright E2E：1 条完整学习闭环通过，包含空库迁移到 `20260710_0011`、两次错题、路径重排、报告、三类 Graph 轨迹和 `390px` 无水平溢出。

## 3. Docker 验证

Phase 12.2 的 Docker 验收命令：

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose exec -T backend python -m alembic current
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -Method Get
```

预期健康检查：

```json
{"status":"ok","service":"edunova-api"}
```

## 4. 浏览器验收

浏览器验收优先使用 `agent-browser`。

Phase 12.2 主流程：

```text
注册示例课程 -> 首页 -> 资料库 -> 课程空间问答 -> 资源工坊
-> 学习路径 -> 练习 -> 报告 -> Markdown 导出
```

验收宽度：

- 桌面宽度。
- `390px` 移动宽度。

验收结论和已知限制记录在 `docs/evidence/PHASE_12_2_ACCEPTANCE.md`。

## 5. 隐私和密钥检查

阶段验收必须确认：

- 仓库未跟踪真实 `.env`。
- 文档不包含真实 API Key、JWT、密码或用户资料。
- Agent trace、报告和导出只保存安全摘要。
- 浏览器验收使用临时账号或示例课程。
- 上传文件、缓存、日志和构建产物不进入提交。

## 6. 已知限制

当前仍未覆盖或未实现：

- OCR 和图片题目识别。
- 旧版 DOC/PPT 和扫描件解析。
- 异步资源任务队列。
- 资料对比结果与期末冲刺联动。
- 剩余 Profile/CourseBuilder/MaterialComparison/ExamSprint/ExportDossier Graph 生产接管。

这些条目是 Phase 14 的历史限制，不再代表当前实现；当前状态以 `STATUS.md` 和下述 Phase 28 记录为准。

## 7. Phase 28 赛题合规与真实证据收口

2026-07-15 实际结果：

- `scripts/test.ps1`：后端 393 项、前端 233 项、离线 AI 评测 10 项通过；编码、Ruff、Alembic `20260715_0025`、OpenAPI 漂移、lint、build 和 Compose 均通过。
- 隔离 Docker E2E：八服务健康，pgvector 与代码执行隔离通过，Playwright 2 项通过，临时容器和卷已清理。
- 真实调用：19 次模型加 1 次搜索；发现 1 条合格 YouTube 视频。SSE 首状态 44.2ms、首 Token 5269ms、AIJob 创建 38.2ms、进度 1053.6ms、三类资源批次 85837.3ms；`contest_readiness --require-live` 通过。
- 供应链：仅运行一次；Python、pnpm/npm 审计无已知漏洞，Trivy 漏洞、密钥和 Dockerfile 配置均为 0 命中。Trivy 未从容器外 Python 环境自动解析许可证，直接依赖许可证由项目脚本独立生成并纳入文档。
- 浏览器：`agent-browser` 验证桌面和 390px 的学习包、真实外部视频 iframe、原平台链接、报告资源使用概览，均无水平溢出。
- 隐私清理：两个临时账号及级联课程、资源、互动和报告数据已删除，仓库只保留聚合指标。

历史风险更新：同步路径 53–62 秒和 nginx 504 已由 Phase 29 的 AIJob/RQ 异步化解决。Phase 31 修复 Provider `output` 包装兼容与可信难点候选后，两组可信画像均以模型增强、无 fallback 完成同一“二叉树遍历”对照，在教学策略与资源模态上出现两项可见差异。外部模型波动仍由安全 fallback 承担，但不再把本轮实证写成不足。

## 8. Phase 31 大型真实教材闭环实战

2026-07-16 实际结果：

- 437 页、25,628,230 字节的整本真实教材经普通用户页面完成上传、Docling 解析、目录确认、建课和完整学习闭环；解析得到 437 页、约 98% 可读页、10 个顶层章、51 个目录条目、479 个切片和 51 个课程知识点。
- 三个临时账号累计 140 次真实 Provider 尝试，未超过 180 次上限；教材正文、模型原始响应、截图和导出均未进入仓库。
- 完整工程门禁通过后端 425 项、前端 238 项、离线 AI 评测 10 项，以及编码、Ruff、Alembic、OpenAPI、lint、build 和 Compose。
- 隔离 Docker E2E 通过八服务健康、pgvector、代码执行隔离和 2 条 Playwright 用例。初次重跑先暴露过期的“全部未评分”断言，随后真实暴露任务托盘遮挡页面主动作；更新部分评分验收并把折叠托盘收为右侧中部 44px 标签后，最终主链通过，临时容器、网络和卷全部删除。
- `agent-browser` 复核 1440px 与 390px，练习设置可点击、Radix 弹窗可关闭、两种宽度均无水平溢出。两组可信画像路径均为模型增强且无 fallback，在策略和资源模态上至少形成两项可见差异。
- 精确删除 3 个临时账号、2 份上传副本、5 份导出、23 个 RQ 任务、4 门临时课程和全部级联数据；原始 PDF 的字节数、修改时间和 SHA-256 均与验收前一致，仓库不保存教材文件指纹。
- 本轮未新增真实性能样本，赛题就绪评测的实时性能证据保持 `evidence_gap`，不使用离线结果替代。
