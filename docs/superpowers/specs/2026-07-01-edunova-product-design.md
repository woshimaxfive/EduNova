# EduNova Product Design

日期：2026-07-01

## 1. 项目定位

EduNova 是面向高校学生的 AI 个性化学习工作台。它不是传统教务系统，也不是简单聊天机器人，而是围绕学生个人持续学习形成闭环：

```text
对话建画像 -> 诊断薄弱点 -> 生成学习资源 -> 规划学习路径
-> AI 辅导答疑 -> 练习评估 -> 更新画像与路径
```

第一版核心用户只有学生。系统中的“教师”由 AI Agent 承担，包括画像分析师、资源生成师、路径规划师、AI 导师、评估官和审核员。

第一版不做完整人类教师端、班级管理、家长端、复杂教务系统、支付课程购买、真实视频生成。第一版必须做强学生学习工作台、人工智能导论知识库、动态学习画像、多智能体资源生成、个性化学习路径、RAG 智能辅导、学习效果评估、Agent 协作轨迹、Docker 部署与后续开源基础。

## 2. 参考项目与差异化

EduNova 的设计参考赛题原文和多个开源项目，但不直接照搬代码。

参考方向：

| 项目 | 借鉴点 | EduNova 的取舍 |
| --- | --- | --- |
| education-agent | A3 功能完整度、画像、资源、路径、题库 | 作为主蓝本参考，但重新做产品边界和技术说明 |
| OpenMAIC | 课堂感、资源展示、互动课堂、导出体验 | 借鉴体验，不把第一版做成完整虚拟课堂系统 |
| AptAdapt / ZhiShu | 学生主线、Agent 分工、A3 功能拆解 | 采用学生端优先路线，后台只做轻量维护能力 |
| A3_study_agent / SparkWeave | 可解释、防幻觉、证据链、运行轨迹 | 强化引用溯源、ReviewAgent 和答辩可解释性 |
| Multi-Agent-Learning-System | 多 Agent、RAG、学习闭环上限参考 | 不照搬重型多服务架构，避免两周内失控 |

EduNova 的差异化目标：

1. 学生端体验优先，不做传统多角色教务平台。
2. 内置人工智能导论课程，同时支持用户上传资料自动建课。
3. 每个 AI 输出有引用来源、审核状态和 Agent 轨迹。
4. 第一版能跑通完整学习闭环，后续能开源部署和多人使用。

## 3. 第一版功能范围

第一版做学生端完整学习闭环，底层保留平台扩展能力。

核心模块：

| 模块 | 第一版能力 |
| --- | --- |
| 学习工作台 | 展示画像摘要、当前课程、今日任务、最近资源、学习进度、Agent 轨迹 |
| 对话式画像 | 通过自然语言问答构建 6-8 维画像，并支持随学习记录更新 |
| 知识库/RAG | 内置人工智能导论课程知识库，并支持用户上传资料入库 |
| 上传资料建课 | 上传 PPTX/PDF/DOCX/Markdown/TXT，解析并生成个人课程 |
| 多智能体资源生成 | 至少生成讲解文档、思维导图、练习题、代码案例、PPT 大纲或视频脚本 |
| 个性化学习路径 | 根据画像、薄弱点、课程知识点生成阶段式学习路径 |
| AI 智能辅导 | 基于知识库、画像和上下文进行问答、追问、解释、错题讲解 |
| 学习效果评估 | 通过练习、问答和资源使用记录生成掌握度与改进建议 |

主演示链路：

```text
学生注册/登录
-> 对话建立画像
-> 选择人工智能导论或上传资料生成课程
-> 多 Agent 生成 5 类学习资源
-> 生成阶段式学习路径
-> 进入 AI 辅导问答
-> 完成练习评估
-> 更新画像和路径
-> 生成学习报告
-> 查看 Agent 轨迹与引用来源
```

## 4. 可扩展边界

第一版不做完整教师端，但不是单人硬编码 demo。底层必须保留扩展点：

| 未来能力 | 第一版预留方式 |
| --- | --- |
| 教师端 | `users.role` 保留角色字段，第一版使用 `student/admin`，后续可加 `teacher` |
| 班级管理 | 设计 `courses`、`course_enrollments`，第一版用于学生个人课程 |
| 教师布置任务 | `learning_tasks` 保留 `created_by`、`source_type` |
| 管理后台 | 保留知识库导入、Agent 日志、系统配置的轻量入口 |
| 家长端 | 评估报告独立存储，后续可加只读授权关系 |
| 多课程扩展 | 第一版主线是人工智能导论，但所有资源绑定 `course_id` |

产品体验上学生端优先；工程结构上保留多用户、多课程、角色权限、日志审计和资源归属。

## 5. 技术架构

第一版技术栈：

| 层 | 技术 |
| --- | --- |
| 前端 | React + TypeScript + Vite |
| UI | Tailwind CSS + Ant Design 或 shadcn/ui |
| 可视化 | ECharts + Mermaid / Markmap |
| 后端 | Python 3.12 + FastAPI |
| 数据校验 | Pydantic |
| ORM | SQLAlchemy |
| AI 编排 | LangGraph |
| RAG | LangChain + pgvector |
| 数据库 | PostgreSQL + pgvector |
| 缓存与进度 | Redis |
| 登录认证 | JWT + bcrypt |
| 流式输出 | SSE |
| PPT 生成 | python-pptx |
| 部署 | Docker Compose + Nginx |
| 测试 | pytest + Vitest + Playwright |

系统结构：

```text
React 学生工作台
        ↓ HTTP/SSE
FastAPI 后端 API
        ↓
业务服务层：画像 / 资源 / 路径 / 辅导 / 评估 / 建课
        ↓
LangGraph 多智能体编排
        ↓
LLM Provider + RAG 知识库 + PostgreSQL + Redis
```

建议目录：

```text
EduNova/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── agents/
│   │   ├── rag/
│   │   └── tasks/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── stores/
│   │   └── visualizations/
├── knowledge_base/
│   └── artificial_intelligence_intro/
├── docs/
├── docker-compose.yml
└── README.md
```

架构原则：

```text
学生端优先
平台能力预留
AI 能力可替换
长任务可追踪
结果可溯源
部署可复现
答辩可解释
```

## 6. 多智能体设计

第一版设计 9 个核心 Agent：

| Agent | 职责 | 输出 |
| --- | --- | --- |
| ProfileAgent | 从对话和学习行为中抽取学生画像 | 画像 JSON、画像变更记录 |
| DiagnosisAgent | 判断知识基础、薄弱点、学习目标 | 薄弱点列表、诊断摘要 |
| CourseBuilderAgent | 根据上传资料识别课程结构、章节和知识点 | 课程大纲、知识点、先修关系 |
| RetrieverAgent | 从课程知识库检索依据 | 引用片段、来源 |
| ResourceAgent | 协调生成多类型学习资源 | 文档、题目、代码案例、PPT 大纲等 |
| PathAgent | 生成阶段式学习路径 | 学习路径 DAG / 任务列表 |
| TutorAgent | 基于画像和知识库进行答疑 | 个性化回答 |
| AssessmentAgent | 根据练习和行为评估学习效果 | 掌握度、报告、建议 |
| ReviewAgent | 检查内容事实性、安全性、完整性 | 审核结果、风险提示 |

资源生成内部包含 5 个 Worker：

```text
DocWorker       讲解文档
MindMapWorker   思维导图
QuizWorker      练习题
CodeWorker      代码实操案例
SlideWorker     PPT 大纲 / 视频脚本
```

典型协作流程：

```text
学生请求
  ↓
Intent Router 判断意图
  ↓
ProfileAgent 读取/更新画像
  ↓
RetrieverAgent 检索知识库依据
  ↓
DiagnosisAgent 判断学习状态
  ↓
ResourceAgent / PathAgent / TutorAgent / AssessmentAgent 执行任务
  ↓
ReviewAgent 审核事实性、安全性、完整性
  ↓
保存结果 + 记录 Agent 运行日志
  ↓
前端展示结果和协作轨迹
```

前端必须展示 Agent 协作轨迹，例如：

```text
画像智能体：已读取你的学习画像
检索智能体：找到 5 条课程依据
诊断智能体：识别 2 个前置薄弱点
资源智能体：生成 5 类学习资源
审核智能体：通过事实性校验
路径智能体：已安排到第 2 天学习任务
```

## 7. 页面与用户流程

正式前端是 AI 学习工作台，不是普通后台页面。建议采用主工作台 Shell：

```text
左侧导航
中间主内容区
右侧 AI Copilot / Agent 轨迹面板
```

页面模块：

| 页面 | 作用 |
| --- | --- |
| 登录/注册 | 学生账号进入系统 |
| 学习工作台 | 总览画像、课程、任务、路径、最近资源 |
| 对话式画像页 | 和 EduNova 对话，生成/更新学习画像 |
| 我的课程页 | 内置课程 + 用户上传生成的课程 |
| 上传建课页 | 上传 PPT/PDF/DOCX/TXT，自动解析成课程 |
| 资源生成页 | 选择课程/知识点，生成 5 类资源 |
| 学习路径页 | 展示阶段式路径、任务、进度 |
| AI 辅导页 | 基于课程知识库问答和追问 |
| 练习评估页 | 做题、批改、薄弱点分析 |
| 学习报告页 | 掌握度、画像变化、下一步建议 |
| 设置页 | 模型 API Key、个人信息、导出数据 |

演示不做三选一，而是三段式组合：

```text
A 内置课程闭环 = 主演示，必须稳
B 现场上传建课 = 创新亮点，必须有
C Agent 协作轨迹 = 技术证明，必须展示
```

## 8. 数据模型

核心数据：

| 数据 | 作用 |
| --- | --- |
| users | 用户账号，第一版主要是学生 |
| courses | 课程，包含内置课程和上传资料生成的课程 |
| course_enrollments | 用户与课程关系，第一版用于个人课程，后续支持班级 |
| course_materials | 用户上传的 PPT/PDF/DOCX/TXT 等资料 |
| knowledge_chunks | 文档切片和向量索引，用于 RAG |
| student_profiles | 学习画像 |
| profile_events | 画像变更日志 |
| learning_paths | 个性化学习路径 |
| learning_tasks | 路径里的任务和知识点任务 |
| generated_resources | 生成的文档、思维导图、题目、代码案例、PPT 大纲等 |
| agent_run_logs | 多智能体运行轨迹 |
| practice_sessions | 一次练习记录 |
| practice_answers | 每道题作答和批改结果 |
| assessment_reports | 学习效果评估报告 |
| chat_sessions | AI 辅导会话 |
| chat_messages | 对话消息 |
| model_settings | 用户自己的模型 Key 和模型选择 |

关键字段：

```text
users.role
courses.owner_id
courses.visibility
course_materials.course_id
knowledge_chunks.course_id
generated_resources.course_id
generated_resources.source_material_ids
learning_paths.course_id
learning_paths.user_id
learning_tasks.source_type
agent_run_logs.trace_id
agent_run_logs.agent_name
assessment_reports.user_id
assessment_reports.course_id
```

画像维度初版 8 个：

1. 专业背景
2. 知识基础
3. 学习目标
4. 认知风格
5. 学习偏好
6. 易错点/薄弱点
7. 学习节奏
8. 动机与兴趣

所有数据都绑定 `user_id`，所有课程内容都绑定 `course_id`，所有 AI 输出都能追溯来源，所有 Agent 执行都留下日志。

## 9. 上传资料自动建课

用户可以上传老师课件、电子书、讲义、复习资料、期末题等资料，EduNova 自动扩展为个人课程。

第一版支持：

| 类型 | 能力 |
| --- | --- |
| PDF | 提取文本、页码、标题线索 |
| PPTX | 提取每页标题、正文、备注 |
| DOCX | 提取标题、段落、表格文本 |
| Markdown | 保留标题层级 |
| TXT | 普通文本切片 |

第一版暂不做扫描版 PDF OCR、图片题目 OCR、复杂公式精确解析、视频文件解析、真实视频生成。

处理流程：

```text
用户上传 PPT/PDF/DOCX/TXT
  ↓
DocumentParser 提取文本
  ↓
CourseBuilderAgent 判断课程名、章节、知识点
  ↓
KnowledgeGraphBuilder 生成知识点依赖关系
  ↓
ChunkingService 切成适合 RAG 的片段
  ↓
EmbeddingService 生成向量
  ↓
写入 PostgreSQL + pgvector
  ↓
生成 Course Overview
  ↓
PathAgent 生成第一版学习路径
```

前端进度展示：

```text
解析文件中...
识别章节结构...
抽取知识点...
建立向量索引...
生成学习路径...
完成
```

自动建课后生成课程名称、课程摘要、章节目录、知识点列表、先修关系、重点难点、初始学习路径。题库生成作为可选增强，第一版可生成少量基础题用于演示。

## 10. 防幻觉与可信学习

EduNova 的可信生成机制是：

```text
检索增强生成 + 引用溯源 + 审核智能体
```

五层防护：

| 层级 | 作用 |
| --- | --- |
| RAG 溯源 | 回答和资源生成前先检索课程资料 |
| 引用绑定 | 关键内容绑定来源文件、页码、章节 |
| ReviewAgent 审核 | 检查事实性、难度、资料一致性 |
| 置信度提示 | 对低依据内容标记“需要复核” |
| 用户反馈闭环 | 学生可以标记“不准确/看不懂/太难” |

每个 AI 输出保存：

```text
citation_refs
review_status
review_notes
confidence_score
```

资料不足时，系统不能硬编，必须提示依据不足，并将通用知识补充标记为“外部扩展内容”。

内容安全包括敏感内容过滤、提示词注入防护、API Key 不入日志、用户上传资料隔离、生成内容不包含隐私、开源时不提交 `.env`。

## 11. 部署、开源与免费使用

第一版部署结构：

```text
Nginx
  ↓
Frontend 静态站点
  ↓
FastAPI Backend
  ↓
PostgreSQL + pgvector
  ↓
Redis
  ↓
文件存储
```

Docker Compose 服务：

```text
frontend
backend
postgres
redis
nginx
```

开源仓库必须包含：

| 文件 | 作用 |
| --- | --- |
| README.md | 项目介绍、功能截图、快速启动 |
| .env.example | 环境变量示例，不含真实密钥 |
| docker-compose.yml | 一键部署 |
| docs/ARCHITECTURE.md | 架构说明 |
| docs/DEPLOYMENT.md | 部署说明 |
| docs/OPEN_SOURCE_NOTICE.md | 参考项目和许可证说明 |
| docs/DEFENSE_QA.md | 答辩问答 |
| LICENSE | 开源许可证 |

免费使用时支持两种模型配置：

```text
模式 A：用户自带 API Key
模式 B：平台统一配置 API Key，但有额度限制
```

第一版建议两个都支持。优先使用用户自己的 Key；没有用户 Key 时使用系统 Key，但通过 Redis 限流和每日额度控制成本。

## 12. 两周里程碑

2026-07-01 到 2026-07-14 完成可运行系统；2026-07-15 到 2026-07-20 做测试、部署、文档、PPT、演示视频。

| 时间 | 目标 | 验收标准 |
| --- | --- | --- |
| Day 1 | 项目骨架 + 文档基线 | 前后端项目创建、Docker Compose 草案、README/架构文档初版 |
| Day 2 | 用户系统 + 工作台框架 | 能注册登录，进入学生工作台 |
| Day 3 | 课程与知识库模型 | 内置人工智能导论课程，课程/资料/知识点表可用 |
| Day 4 | 上传资料自动建课 v1 | 支持上传 PDF/PPTX/DOCX/TXT，能解析并生成课程结构 |
| Day 5 | RAG 检索 | 课程资料切片、向量化、问答能引用来源 |
| Day 6 | 对话式画像 | 6-8 维画像生成、保存、展示、更新 |
| Day 7 | 多智能体资源生成 | 生成 5 类资源，并记录 Agent 轨迹 |
| Day 8 | 学习路径规划 | 根据画像和知识点生成路径、任务、进度 |
| Day 9 | AI 辅导问答 | 基于课程资料、画像和 RAG 的个性化答疑 |
| Day 10 | 练习与学习评估 | 题目作答、批改、掌握度、学习报告 |
| Day 11 | 防幻觉审核 + 引用溯源 | ReviewAgent、置信度、低依据提示 |
| Day 12 | 前端体验打磨 | 工作台、资源卡片、路径图、Agent 轨迹更像产品 |
| Day 13 | 部署与测试 | Docker Compose 跑通，核心链路测试通过 |
| Day 14 | 冻结功能 | 修 bug，准备提交物基础版本 |

7月15日后：

| 时间 | 目标 |
| --- | --- |
| 7月15-16日 | 系统开发说明书、测试说明书、部署说明 |
| 7月17日 | 演示 PPT |
| 7月18日 | 演示视频脚本和录制 |
| 7月19日 | 全流程彩排、补截图、修体验问题 |
| 7月20日前 | 打包提交 |

每天结束必须有一个可见版本。每个核心模块都要有答辩解释。不要做无关教师端、复杂运营功能或无法演示的技术堆叠。

## 13. 风险控制

| 风险 | 处理 |
| --- | --- |
| 上传建课解析复杂 | 第一版做文本解析，OCR 后置 |
| 视频生成太重 | 第一版做视频脚本、分镜、PPT 大纲 |
| 多智能体慢 | 使用异步任务和进度展示 |
| 模型不稳定 | 提供 mock/fallback 演示模式 |
| UI 来不及 | 优先学生工作台主链路 |
| 答辩压力大 | 同步维护 `docs/DEFENSE_QA.md` |
| API 成本高 | 用户级 Key、系统 Key 限额、Redis 限流 |
| 数据串用 | 所有数据按 `user_id` 和 `course_id` 隔离 |

## 14. 设计结论

EduNova 第一版的正式基线是：

```text
面向学生个人的 AI 学习工作台
+ 上传资料自动建课
+ 多智能体资源生成
+ RAG 引用溯源
+ 学习路径与评估闭环
+ 可部署、可开源、可答辩解释
```

下一步应基于本设计文档编写实施计划，然后进入项目骨架搭建。

