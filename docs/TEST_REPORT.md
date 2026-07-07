# EduNova 测试报告

更新时间：2026-07-05

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
```

`scripts/test.ps1` 覆盖：

- UTF-8 无 BOM 编码检查。
- 后端 pytest。
- 前端 ESLint。
- 前端 Vitest。
- Vite 生产构建。
- Alembic head 检查。
- Docker Compose 配置校验。

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

- 完整浏览器 E2E 自动化套件。
- OCR 和图片题目识别。
- 旧版 DOC/PPT 和扫描件解析。
- 异步资源任务队列。
- 资料对比结果与期末冲刺联动。
- 错题驱动深度薄弱点追溯。

这些限制不阻塞当前 Phase 13.2 增强，但会进入 Phase 13 后续打磨清单。PDF/DOCX/PPTX 文本解析、主页联网/深思/浏览器语音和 Markdown/PDF/DOCX 异步导出已进入自动化验证范围。
