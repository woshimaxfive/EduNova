# EduNova 项目看板

更新时间：2026-07-01

## 1. 当前原则

EduNova 当前阶段坚持“基础不牢，地动山摇”的开发原则。

在大规模写功能前，必须先补齐：

- 需求规格。
- 架构设计。
- API 设计。
- 数据库设计。
- 测试计划。
- 项目看板。
- 编码规范。
- 安全与隐私设计。
- 部署和开源合规方案。

第一版目标不是做一个能临时演示的壳子，而是做一个后续可以继续扩展、开源和部署给同学使用的软件。

## 2. 当前状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 赛题原文 | 已存在 | `docs/软件杯A3赛题.txt` |
| 产品设计 | 已完成 | `docs/superpowers/specs/2026-07-01-edunova-product-design.md` |
| 实施计划 | 已完成 | `docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md` |
| 中文导读 | 已完成 | `docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md` |
| 测试计划 | 已完成 | `docs/TEST_PLAN.md` |
| 需求规格 | 本轮新增 | `docs/REQUIREMENTS.md` |
| 架构设计 | 本轮新增 | `docs/ARCHITECTURE.md` |
| API 设计 | 本轮新增 | `docs/API.md` |
| 数据库设计 | 本轮新增 | `docs/DATABASE_DESIGN.md` |
| 项目看板 | 本轮新增 | `docs/PROJECT_BOARD.md` |
| 仓库规则 | 本轮新增 | `AGENTS.md` |
| 编辑器规则 | 本轮新增 | `.editorconfig` |
| 环境变量示例 | 本轮新增 | `.env.example` |
| 编码检查脚本 | 本轮新增 | `scripts/verify_encoding.ps1` |
| 总测试脚本 | 本轮新增 | `scripts/test.ps1` |
| 安全基线 | 本轮新增 | `docs/SECURITY.md` |
| 风险登记册 | 本轮新增 | `docs/RISK_REGISTER.md` |
| 后端骨架 | 进行中 | FastAPI 最小应用、`/api/health`、pytest 与编码检查已完成 |

## 3. 里程碑

| 里程碑 | 时间 | 目标 | 状态 |
| --- | --- | --- | --- |
| M0 基础设计 | 7 月 1 日 | 需求、架构、API、数据库、测试、看板 | 进行中 |
| M1 工程骨架 | 7 月 1-2 日 | 后端骨架、前端骨架、Docker、编码检查 | 进行中 |
| M2 数据与课程 | 7 月 2 日 | 核心表、迁移、人工智能导论课程包 | 未开始 |
| M3 登录与工作台 | 7 月 3 日 | 注册登录、学生工作台 | 未开始 |
| M4 上传建课与 RAG | 7 月 4-5 日 | 上传解析、自动建课、检索引用 | 未开始 |
| M5 画像与资源生成 | 7 月 6-7 日 | 对话画像、多智能体、5 类资源 | 未开始 |
| M6 学习闭环 | 7 月 8-10 日 | 路径、掌握度、辅导、练习、报告 | 未开始 |
| M7 增强功能 | 7 月 11-12 日 | 期末冲刺、资料对比、导出、Demo Mode | 未开始 |
| M8 验收与冻结 | 7 月 13-14 日 | Docker、测试、浏览器证据、功能冻结 | 未开始 |
| M9 提交材料 | 7 月 15-20 日 | 文档、PPT、视频、提交包 | 未开始 |

## 4. 当前待办

### P0 必须先做

- [x] 提交当前基础文档。
- [x] 创建编码检查脚本 `scripts/verify_encoding.ps1`。
- [x] 创建总测试脚本 `scripts/test.ps1`。
- [x] 创建基础 README。
- [x] 创建 `.env.example`。
- [x] 搭建 FastAPI `/api/health`。
- [ ] 搭建 Docker Compose 草案。

### P1 紧接着做

- [ ] 建立后端目录结构。
- [ ] 建立前端目录结构。
- [ ] 建立数据库迁移。
- [ ] 导入人工智能导论课程包。
- [ ] 实现注册登录。
- [ ] 实现学生工作台。

### P2 随开发推进

- [x] 补 `docs/SECURITY.md`。
- [ ] 补 `docs/AGENT_DESIGN.md`。
- [ ] 补 `docs/RAG_DESIGN.md`。
- [ ] 补 `docs/UI_UX_DESIGN.md`。
- [ ] 补 `docs/DEVELOPMENT_GUIDE.md`。
- [ ] 补 `docs/DEPLOYMENT.md`。
- [ ] 补 `docs/OPEN_SOURCE_NOTICE.md`。
- [ ] 补 `docs/USER_GUIDE.md`。
- [ ] 补 `docs/DEFENSE_QA.md`。
- [x] 补 `docs/RISK_REGISTER.md`。

## 5. 风险清单

| 风险 | 等级 | 应对 |
| --- | --- | --- |
| 功能范围继续膨胀 | 高 | 严格以需求规格和实施计划为准 |
| 上传资料解析不稳定 | 高 | 第一版优先支持文本型资料，OCR 后置 |
| 模型 API 不稳定 | 高 | Demo Mode 和 fallback Provider |
| 多智能体变成空概念 | 高 | 每次任务记录 agent_run_logs 和 trace_id |
| RAG 没有引用展示 | 高 | AI 输出验收必须检查 citation_refs |
| 前端做成普通后台 | 中 | UI 设计坚持学生学习工作台 |
| 单人开发时间不足 | 高 | 每天必须有可运行版本，先主链路后增强 |
| 开源协议遗漏 | 中 | 建立 OPEN_SOURCE_NOTICE |
| API Key 泄露 | 高 | `.env` 忽略、日志脱敏、提交前敏感词扫描 |
| 文档和代码不一致 | 中 | 每个里程碑结束同步文档 |

## 6. 每日工作规则

每天开始：

```text
1. 查看 PROJECT_BOARD 当前 P0/P1。
2. 查看 git status。
3. 确认当天只推进一个主目标。
4. 先写或更新测试与验收标准。
5. 检查相关文档是否需要随本轮开发同步更新。
```

每天结束：

```text
1. 运行可用检查。
2. 更新 PROJECT_BOARD。
3. 记录完成内容和未解决问题。
4. 提交一个清晰 commit。
5. 保证下一天能接着做。
6. 如果代码、接口、数据库、架构、测试、部署或风险发生变化，同步更新对应文档。
```

## 7. 完成定义

一个任务只有同时满足以下条件才算完成：

1. 功能或文档已经落到文件。
2. 相关测试或检查已经运行。
3. 没有违反 UTF-8 无 BOM、中文不转义规则。
4. 没有提交真实密钥。
5. 和需求规格不冲突。
6. 必要时更新相关文档。
7. 已经提交到 Git。

文档同步是完成定义的一部分。后续开发中，如果实现和文档不一致，不能把任务标记为完成。

## 8. 下一步执行建议

当前最合理的下一步：

```text
1. 提交并推送 Phase 1A 最小后端骨架。
2. 进入 Phase 1B：Docker Compose 草案。
3. 在 Phase 1B 中补 PostgreSQL、Redis 和后端服务健康检查。
4. 同步更新 README、测试计划和项目看板。
```

这一步完成后，再进入数据库、前端和 AI 功能开发。
