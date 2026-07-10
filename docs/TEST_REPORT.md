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

这些限制不阻塞当前 Phase 14。错题证据、已有路径重排、报告趋势、课程 pgvector SQL 候选和隔离 Docker E2E 已进入自动化验证范围。
