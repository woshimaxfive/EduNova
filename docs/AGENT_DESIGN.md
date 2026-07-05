# EduNova Agent 设计说明

更新时间：2026-07-05

## 1. 定位

EduNova 的 Agent 设计服务于学生学习闭环，不是为了展示“多智能体”概念本身。第一版重点是让每一步 AI 或规则推理都有输入边界、输出摘要、证据来源和失败恢复方式。

当前 Phase 12.2 的真实状态：

- 已有 `agent_run_logs` 表和 `/api/v1/agents/traces/{trace_id}` 查询接口。
- 资源生成流程会写入 `profile -> retrieve -> diagnosis -> resource -> review -> persist` 六步安全日志。
- LangGraph 已作为后续编排基础存在，但还不是所有学习流程的生产编排引擎。
- 课程问答、资源生成、路径、练习、报告和导出均遵守隐私安全摘要原则。

## 2. 角色边界

| 角色或服务 | 当前职责 | 当前实现状态 |
| --- | --- | --- |
| ProfileAgent / ProfileService | 维护用户级 8 维学习画像，沉淀画像事件 | 已实现确定性画像抽取和画像事件 |
| RetrievalAgent / RAG Service | 在当前用户课程内做关键词、向量和混合检索 | 已实现课程 RAG、引用和本地 embedding fallback |
| TutorAgent / TutorSessionService | 处理主页普通问答和课程 RAG 问答，保存会话、引用和 trace | 已实现非流式与 SSE 流式课程问答 |
| WeaknessTracker | 把课程问答候选事件和练习评估沉淀为课程级弱点队列 | 已实现 pending、confirmed、reviewing、completed、dismissed |
| ResourceAgent / ResourceService | 基于课程引用生成 5 类课程资源，模型只做可选增强 | 已实现可用稿优先、质量分和 trace |
| PathAgent / PathService | 根据课程知识点、已确认弱点、资源和画像生成学习路径 | 已实现课程级 active 路径和任务状态更新 |
| AssessmentAgent / PracticeService | 生成练习、确定性批改并反哺掌握度和弱点队列 | 已实现单选、多选、简答第一刀 |
| ReportAgent / ReportService | 聚合课程、练习、掌握度、弱点和建议生成学习报告 | 已实现课程学习报告 |
| ExportService | 聚合课程学习档案并导出 Markdown | 已实现同步 Markdown 返回 |

## 3. Agent 状态

共享状态字段在 `backend/app/agents/schemas.py` 中定义，核心字段包括：

```text
trace_id
user_id
course_id
knowledge_point_id
intent
profile
retrieved_chunks
diagnosis
generated_resources
review_result
errors
```

这些字段是后续 LangGraph 真正接管生成流程的基础。当前可以把它理解为“可观测骨架”：状态结构和节点名称已经稳定，生产主链路仍主要由各业务 service 确定性执行。

## 4. Trace 白名单

Agent 日志只能记录安全摘要。

允许记录：

- `trace_id`、`course_id`、`knowledge_point_id`。
- Agent 名称、步骤序号、状态、耗时。
- 输入摘要和输出摘要。
- 引用的知识点、章节、来源标题、页码和短摘录。
- 质量分、审核状态、生成模式、错误类型。

禁止记录：

- 完整系统提示词。
- 完整模型输入。
- API Key、JWT、密码和连接密钥。
- 完整用户画像原文。
- 完整上传资料原文。
- 完整用户作答原文。

## 5. 失败恢复

EduNova 的第一版坚持确定性可用稿优先：

- 模型未配置时，课程资源、路径、练习、报告和导出仍应尽量基于课程引用和规则产出可解释结果。
- 模型调用失败时，不把模板占位伪装成模型结果。
- 资料依据不足时，用 `low_evidence` 或明确空状态表达，不编造引用。
- 课程问答没有依据时提示资料不足，不伪造课程引用。

## 6. 答辩解释口径

可以这样解释 EduNova 的多智能体：

```text
EduNova 第一版不是把所有逻辑都交给大模型，而是把学生学习链路拆成画像、检索、资源、路径、评估、报告等可审计角色。
每个角色都有明确的数据边界和证据来源，关键流程会留下 trace。
模型负责增强表达，规则和课程引用负责保证结果可复现、可解释、可在无模型环境下演示。
```

## 7. 后续打磨

- 资源工坊直接展示资源生成 trace。
- AgentTimeline 展示更多白名单 metadata。
- 评估 LangGraph 真正接管资源生成或路径生成编排。
- 把资料对比结果作为期末冲刺和路径排序的证据来源。
