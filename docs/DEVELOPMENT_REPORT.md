# EduNova 开发报告

更新时间：2026-07-10

## 1. 项目概述

EduNova 是面向高校学生的 AI 个性化学习空间，对应第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版目标是跑通学生学习闭环：

```text
注册登录 -> 示例课程或上传资料 -> 课程 RAG 问答 -> 学习画像
-> 弱点追踪 -> 资源生成 -> 学习路径 -> 练习评估
-> 学习报告 -> Markdown/PDF/DOCX 学习档案导出
```

## 2. 系统设计

EduNova 采用前后端分离和 Docker Compose 部署：

- 前端：React、TypeScript、Vite、React Router、React Query。
- 后端：FastAPI、SQLAlchemy、Alembic、Pydantic。
- 数据：PostgreSQL、pgvector、Redis、本地文件存储。
- AI：OpenAI-compatible Chat Completions、SSE、OpenAI-compatible Embeddings、pgvector SQL 候选与关键词 fallback。
- Agent 编排：LangGraph 学习闭环生产编排，Service 层作为 API 边界和依赖装配层。
- 部署：backend、export-worker、frontend、postgres、redis、nginx 六服务。

核心设计原则：

- 当前用户数据强隔离。
- 课程资料和引用优先。
- 确定性可用稿优先，模型增强可选。
- Agent trace 只记录安全摘要。
- 文档和实现同步演进。

## 3. 阶段成果

| 阶段 | 成果 |
| --- | --- |
| Phase 0-2 | 项目文档、工程骨架、数据库迁移、核心表和内置课程包 |
| Phase 3 | 学生端主页、资料库、课程空间和核心页面 |
| Phase 4 | 注册登录、首页 summary、主页会话和真实资料库 |
| Phase 5 | TXT/Markdown 规则建课、课程 RAG 检索和课程会话引用 |
| Phase 6 | 模型配置、流式课程回答、embedding 和课程空间双模式 |
| Phase 7 | 用户级画像、画像事件、课程级弱点队列和状态流转 |
| Phase 8/13 增强 | Agent trace、六类结构化资源、并行 Worker、交互渲染和真实 PPTX |
| Phase 9 | 课程级学习路径、规则掌握度图和复习时间 |
| Phase 10 | 练习生成、确定性批改、弱点反哺和学习报告 |
| Phase 11 | 期末冲刺计划和资料对比第一刀 |
| Phase 12.1 | Markdown 学习档案导出 |
| Phase 12.2 | 交付基线、开源准备和验收证据 |
| Phase 13.1 | 全学习闭环 LangGraph 生产编排、学习产物 trace 字段和前端轨迹入口 |
| Phase 13.2 | PDF/DOCX/PPTX 资料解析、主页联网/深思/浏览器语音、Markdown/PDF/DOCX 异步导出 |
| Phase 14 | PathPlanningGraph、AssessmentGraph、ReportGraph，错题证据、路径回流、报告趋势、课程 pgvector SQL 和隔离 E2E |

## 4. 核心创新

### 4.1 课程证据驱动

课程问答、资源、路径、练习和报告都尽量引用当前用户课程资料、知识点、章节和安全摘录。资料不足时不编造结论。

### 4.2 用户级画像 + 课程级状态

用户级画像只保留一份，课程差异通过课程学习状态表达，包括弱点、掌握度、复习队列、路径和资源推荐。

### 4.3 模型无关可用资源

资源生成不依赖强模型。系统先构造确定性可用稿，再让模型做可选增强；模型失败时仍保留可读、可练、可复用的资源。

### 4.4 LangGraph 可观测编排

当前六条生产主链路由真实 LangGraph runner 接管：主页问答、课程问答、资源生成、路径、练习评估和报告。画像、资料建课/对比、冲刺和导出仍保留服务逻辑与兼容 trace。前端通过共享披露组件展示真实节点轨迹；trace 不记录系统提示词、完整模型输入、API Key、完整资料原文或完整用户画像原文。

### 4.5 练习和报告反哺

练习结果会精确绑定到作答证据，更新课程级弱点与掌握度，并用独立路径 Graph 重排已有路径；报告确定性聚合最近 5 次练习、趋势和证据，模型只增强解释。

## 5. 当前能力

当前已具备：

- 真实用户认证和受保护路由。
- 注册时选择示例课程。
- 资料上传、列表和 TXT/Markdown/PDF/DOCX/PPTX 建课。
- 课程 RAG 问答、SSE 流式回答和引用持久化。
- 8 维学习画像和画像事件。
- 课程级弱点队列和状态流转。
- 六类结构化课程资源生成与审核。
- 学习路径和掌握度图。
- 练习评估和学习报告。
- 期末冲刺计划。
- 同课程资料对比。
- Markdown/PDF/DOCX 学习档案异步导出，旧 Markdown 同步接口保留兼容。
- 学习闭环 LangGraph 生产编排和安全 trace 查询。
- Docker Compose 一键启动。

## 6. 当前限制

当前没有实现：

- OCR 和图片题目识别。
- 旧版 DOC/PPT 和扫描件解析。
- 异步资源任务队列。
- 资料对比结果持久化和期末冲刺联动。
- Profile、CourseBuilder、MaterialComparison、ExamSprint 和 ExportDossier 的真实 Graph 接管。
- 完整教师端、家长端、支付和移动端 App。

## 7. 后续计划

Phase 14 后进入 Verification and Hardening / 产品打磨：

- 扩展隔离 Docker E2E 的失败分支和六 Graph 跨页面覆盖。
- 汇总并修复 Phase 12.2 验收发现的问题。
- 打磨资源质量、路径排序、练习题质量和报告表达。
- 优化移动端和交互细节。
- 打磨导出版式、Graph 轨迹视觉和浏览器验收证据。
