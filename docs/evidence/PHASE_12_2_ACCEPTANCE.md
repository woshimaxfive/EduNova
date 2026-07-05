# Phase 12.2 验收证据

日期：2026-07-05

## 1. 基线

| 项目 | 结果 |
| --- | --- |
| 分支 | `feature/edunova-foundation` |
| Phase 12.2 起点提交 | `5d7f8ca feat(exports): add markdown learning dossier` |
| 本阶段性质 | 交付基线、开源准备、验收证据和提交前文档 |
| 业务功能变更 | 无新增业务功能 |
| 许可证 | MIT License |

Phase 12.2 不是最终封版，而是继续打磨前的稳定基线。后续进入 Phase 13：Verification and Hardening / 产品打磨。

## 2. 自动化验证

| 命令 | 结果 |
| --- | --- |
| `.\scripts\verify_encoding.ps1` | 通过，`encoding check passed` |
| `.\scripts\test.ps1` | 通过 |
| `git diff --check` | 通过 |

`scripts/test.ps1` 结果摘要：

```text
Backend: 161 passed, 1 warning
Alembic: 20260704_0006 (head)
Frontend: 15 test files passed, 120 tests passed
Vite build: passed
Docker Compose config: passed
```

已知构建提示：

```text
Vite 提示 index chunk 超过 500 kB。
```

这是既有体积提示，不阻塞 Phase 12.2。后续可在 Phase 13 评估路由级拆包。

## 3. Docker 验证

| 命令 | 结果 |
| --- | --- |
| `docker compose config --quiet` | 通过 |
| `docker compose up --build -d` | 通过，五服务启动 |
| `docker compose exec -T backend python -m alembic current` | `20260704_0006 (head)` |
| `http://127.0.0.1:8080/api/health` | `{"status":"ok","service":"edunova-api"}` |

服务状态摘要：

```text
postgres healthy, redis healthy, backend healthy, frontend healthy, nginx healthy
backend: 8000
nginx: 8080
postgres: 5432
redis: 6379
```

## 4. 浏览器验收

工具：`agent-browser`

会话：`edunova-phase12-2`

地址：

```text
http://127.0.0.1:8080
```

使用临时本地验收账号：

```text
昵称：Phase 12 验收
邮箱：phase12-2-202607052103@example.local
starter_mode：带一个示例课程开始
```

验收链路：

| 步骤 | 结果 |
| --- | --- |
| 注册示例课程 | 通过，注册后进入 `/app`，首页显示“人工智能导论” |
| 资料库 | 通过，`/app/library` 显示内置 Markdown 资料，资料对比区域可见 |
| 课程空间 | 通过，`/app/courses/43` 显示问答模式、待复习弱点、课程行动入口和输入区 |
| 课程问答 | 通过，发送“我不懂机器学习和深度学习的区别...”后生成课程历史、引用来源和待复习弱点 |
| 资源工坊 | 通过，`/app/studio` 读取课程和知识点，生成资源后显示“本地可用稿”和资源卡 |
| 学习路径 | 通过，`/app/path?course_id=43` 生成 12 个学习任务，掌握度图和期末冲刺区域可见 |
| 练习 | 通过，`/app/practice?course_id=43` 生成 5 题练习，提交后出现得分反馈 |
| 报告 | 通过，`/app/reports?course_id=43` 生成课程学习报告，显示分数、薄弱点和掌握度变化 |
| Markdown 导出 | 通过，点击“导出学习档案”后显示“已生成 Markdown 学习档案。” |

移动宽度验收：

| 页面 | 视口 | 结果 |
| --- | --- | --- |
| `/app/reports?course_id=43` | `390 x 844` | `clientWidth=390`，`scrollWidth=390`，无水平溢出 |
| `/app/courses/43` | `390 x 844` | `clientWidth=390`，`scrollWidth=390`，无水平溢出 |

## 5. 安全和隐私检查

检查结果：

- `.env` 未被 Git 跟踪，仍处于 ignored 状态。
- `frontend/dist`、`output`、`var` 等运行产物未进入提交。
- 文档范围敏感信息 PCRE 扫描无命中。
- 全仓扫描命中的 `sk-user-secret`、`spark-secret`、`Password123` 等均为测试夹具或源码变量名，不是真实密钥。
- 新增文档只使用示例账号、示例密钥和安全说明。

本阶段未提交：

- 真实 API Key。
- 真实 JWT。
- 真实用户资料。
- 用户上传资料原文。
- 系统提示词和完整模型输入。
- 浏览器下载的 Markdown 文件。

## 6. 已知限制

Phase 12.2 后仍保留以下后续打磨项：

- 完整浏览器 E2E 自动化套件。
- PDF/PPTX/DOCX 深度解析。
- OCR 和图片题目识别。
- PDF/Word 导出。
- 异步资源或导出任务队列。
- 资料对比结果与期末冲刺联动。
- 错题驱动深度薄弱点追溯。
- 资源工坊直接展示资源生成 trace。
- AgentTimeline 展示更多白名单 metadata。
- LangGraph 真正接管生产生成编排。

## 7. 结论

Phase 12.2 可作为当前交付基线：系统可通过 Docker 默认入口启动，自动化验证通过，核心学生学习主链路可在浏览器中从注册示例课程走到报告和 Markdown 导出，新增开源与提交前文档已补齐，且未发现真实密钥或用户资料进入仓库。
