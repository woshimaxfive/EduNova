# EduNova

EduNova 是面向高校学生的 AI 个性化学习工作台，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

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
| [产品设计](docs/superpowers/specs/2026-07-01-edunova-product-design.md) | EduNova 做什么 |
| [实施计划](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md) | EduNova 怎么开发 |
| [中文阅读版](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md) | 实施计划中文导读 |
| [需求规格](docs/REQUIREMENTS.md) | 功能范围和验收标准 |
| [架构设计](docs/ARCHITECTURE.md) | 系统模块和技术架构 |
| [API 设计](docs/API.md) | 前后端接口约定 |
| [数据库设计](docs/DATABASE_DESIGN.md) | 数据表和关系 |
| [测试计划](docs/TEST_PLAN.md) | 测试范围和验收流程 |
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

代码实现尚未开始。下一步是搭建工程骨架、编码检查脚本、FastAPI 健康检查和 Docker Compose 草案。
