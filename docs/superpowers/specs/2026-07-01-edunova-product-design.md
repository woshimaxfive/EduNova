# EduNova Product Design

日期：2026-07-01

## 1. 项目定位

EduNova 是面向高校学生的 AI 个性化学习空间。它不是传统教务系统，也不是简单聊天机器人，而是围绕学生个人持续学习形成闭环：

```text
对话建画像 -> 诊断薄弱点 -> 生成学习资源 -> 规划学习路径
-> AI 辅导答疑 -> 练习评估 -> 更新画像与路径
```

第一版核心用户只有学生。系统中的“教师”由 AI Agent 承担，包括画像分析师、资源生成师、路径规划师、AI 导师、评估官和审核员。

第一版不做完整人类教师端、班级管理、家长端、复杂教务系统、支付课程购买、真实视频生成。第一版必须做强学生 AI 学习空间、人工智能导论知识库、动态学习画像、多智能体资源生成、个性化学习路径、RAG 智能辅导、学习效果评估、Agent 协作轨迹、Docker 部署与后续开源基础。

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

前端体验额外参考：

| 参考方向 | 借鉴点 | EduNova 的取舍 |
| --- | --- | --- |
| ChatGPT | 对话式主入口、工作区协作 | AI 输入区成为主操作入口，可位于中心或底部 |
| NotebookLM | 资料源、AI 问答、Studio 输出 | 借鉴 Sources + Studio 结构，改造成课程学习闭环 |
| Apple / Google / Xiaomi | 内容优先、轻材质、表达性动效、流动空间感 | 华丽但克制，避免满屏光效和装饰性粒子 |
| Mobbin / Figma 模板 | 真实产品流、教育和 AI 交互细节 | 只借鉴结构和流程，不复制商业模板视觉与素材 |
| Carbon for AI | AI 标识、引用、解释和风险提示 | 用于证据层、Agent 轨迹和低依据提示 |

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
| AI 学习空间 | 首页以 AI 对话、主页历史、资料库和最近课程为主；课程空间再展示画像摘要、知识画布、今日任务、学习进度、Studio 输出和证据层 |
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
| 多课程扩展 | 第一版主线是人工智能导论；课程内资源绑定 `course_id`，用户资料库资料先绑定 `user_id`，再加入一个或多个课程 |

产品体验上学生端优先；工程结构上保留多用户、多课程、角色权限、日志审计和资源归属。

## 5. 技术架构

第一版技术栈：

| 层 | 技术 |
| --- | --- |
| 前端 | React + TypeScript + Vite |
| UI | Tailwind CSS + 自定义设计 token + Radix UI / shadcn/ui 按需组件 |
| 动效 | Motion + CSS reduced motion |
| 可视化 | React Flow / 自定义 SVG、ECharts、Mermaid / Markmap |
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
React 学生学习空间
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

## 7. 前端体验与用户流程

正式前端是 AI 学习空间，不是普通后台页面。Phase 3 详细设计基线见 `docs/UI_UX_DESIGN.md`，路由、登录注册、Demo 入口和首次进入流程见 `docs/FRONTEND_ROUTING_DESIGN.md`。

2026-07-01 Phase 3 重新收束后，主界面结构改为：

```text
GPT 式贴边可收起主页侧栏
中央 AI 学习对话入口
主页历史
侧栏个人资料 / 设置 / 退出登录
输入区资料库浮层入口和文件上传入口
下方最近学习轻量列表 / 最近课程入口
发送后主页对话流和下方输入区
回答下方可展开引用、学习路径建议和 Agent 过程
```

P3.7 起，主界面和学生端核心页面上的主要按钮必须有可见反馈。未接真实 API 的能力先显示本地演示态说明，不能保持空点击，也不能伪装成真实上传、真实联网搜索、真实 AI 生成或真实导出。主页输入区使用 Enter 发送、Shift+Enter 换行；联网搜索和深度思考必须有明确激活态。

P3.9 起，应用入口统一为贴边工作区侧栏：资料库、课程空间、Studio、学习画像、AI 辅导、练习、学习报告和系统设置复用同一套应用外壳；AI 辅导、练习和学习报告仍可从课程空间行动入口进入，保证核心页面可发现但不把顶部做成功能清单。

后续主页视觉微调不在应用内保留开发调参页；以截图或手绘标注作为输入，再同步到正式页面代码。

明确不采用：

```text
固定左侧后台菜单
指标卡片堆
普通管理系统三栏布局
右下角客服式 AI 助手
纯营销首页
```

页面模块：

| 页面或区域 | 作用 |
| --- | --- |
| 登录/注册 | 学生账号进入系统 |
| 学习主页 | 总 AI 学习入口，承载主页历史、侧栏账号入口、资料选择、上传、生成课程和最近课程 |
| 课程空间 | 承载某一课程内的对话、课程资料、学习画布、路径、练习、资源和证据层 |
| AI 输入区 | 通过自然语言触发上传建课、资源生成、错题解释、复习规划和报告整理 |
| 资料库 | 文件库式管理独立资料，支持搜索、查看引用、作为主页对话参考、加入课程或生成课程 |
| Studio | 生成和查看讲解、练习、思维导图、复盘报告、PPT 大纲等资源 |
| 证据层 | 展示引用来源、Agent 轨迹、ReviewAgent 结论、低依据提示和质量评分 |
| 对话式画像 | 和 EduNova 对话，生成或更新学习画像 |
| AI 辅导 | 基于课程知识库问答和苏格拉底追问 |
| 练习评估 | 做题、批改、薄弱点分析 |
| 学习报告 | 掌握度、画像变化、下一步建议和学习档案导出 |
| 设置 | 模型 API Key、个人信息、导出数据 |

演示不做三选一，而是三段式组合：

```text
A 内置课程闭环 = 主演示，必须稳
B 现场上传建课 = 创新亮点，必须有
C Agent 协作轨迹 = 技术证明，必须展示
```

入口体验要求：

```text
登录页不是后台登录框
注册页只收集必要账号信息
注册页示例课程入口清晰可见；后续独立 Demo Mode 不混入登录页主流程
首次进入用轻量引导建立画像或课程上下文
未登录访问应用区必须回到登录页
```

## 8. 数据模型

核心数据：

| 数据 | 作用 |
| --- | --- |
| users | 用户账号，第一版主要是学生 |
| courses | 课程，包含内置课程和上传资料生成的课程 |
| course_enrollments | 用户与课程关系，第一版用于个人课程，后续支持班级 |
| materials | 用户独立资料库中的 PPT/PDF/DOCX/TXT 等资料，后续新增 |
| course_materials | 当前 Phase 2 已落地的课程资料表，后续逐步迁移 |
| course_material_links | 课程与独立资料的关联表，支持同一资料加入多个课程，后续新增 |
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
materials.user_id
course_material_links.course_id
course_material_links.material_id
course_materials.course_id  当前 Phase 2 课程资料表字段，后续由 course_material_links 承担多课程关联
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

所有用户私有数据都绑定 `user_id`，所有课程内内容都绑定 `course_id`，主页对话和独立资料库可以先不绑定课程；所有 AI 输出都能追溯来源，所有 Agent 执行都留下日志。

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

## 12. 增强设计

以下增强点不改变第一版学生端优先的范围，但会提升比赛展示、答辩解释和后续开源价值。

### 12.1 演示与评审模式

系统提供 `Demo Mode`，让评委和老师无需先读代码，也能快速看懂完整价值。

Demo Mode 包含：

```text
内置演示账号
内置人工智能导论课程
内置样例资料与题目
一键走完画像 -> 资源 -> 路径 -> 辅导 -> 评估
展示 Agent 轨迹、引用来源和审核结果
```

Demo Mode 不是伪造数据，而是预置一套稳定的演示输入和 fallback 结果。当模型 API 不稳定时，系统可以使用标记为 `demo_fallback` 的缓存结果保证演示不中断。

### 12.2 Agent 可观测性

每次多智能体任务都生成 `trace_id`，所有 Agent 执行过程可追踪。

记录内容：

```text
trace_id
agent_name
step_index
input_summary
output_summary
duration_ms
status
citation_refs
review_status
error_message
```

前端证据层中的 Agent 轨迹展示：

```text
任务开始
画像智能体读取画像
检索智能体找到证据
资源智能体生成内容
审核智能体完成事实性校验
路径智能体更新任务
任务完成
```

这样答辩时可以证明 EduNova 的多智能体是可观测、可解释、可复盘的。

### 12.3 课程模板生态

为后期开源共建，EduNova 支持课程包导入导出。

课程包格式：

```text
course-pack/
├── course.json
├── knowledge_points.json
├── seed_questions.json
├── materials/
│   ├── chapter-01.pdf
│   └── chapter-02.pptx
└── README.md
```

用途：

1. 官方仓库内置“人工智能导论”课程包。
2. 同学可以贡献“数据结构”“操作系统”“高等数学”等课程包。
3. 用户可以导出自己的个人课程包。
4. 比赛提交时可以把课程包作为数据集/知识库材料提交。

第一版先实现内部课程模板结构，完整导入导出可以在基础功能稳定后补齐。

### 12.4 学习证据链

学习画像和评估报告不能凭空生成，必须能解释依据。

证据来源：

```text
画像对话
练习作答
错题记录
AI 问答
资料阅读
资源使用反馈
学习路径完成情况
```

画像更新必须记录：

```text
profile_event_id
dimension
old_value
new_value
reason
evidence_refs
created_at
```

学习报告必须能回答：

```text
为什么判断这个学生基础薄弱？
为什么推荐这个知识点？
为什么把这个任务排在前面？
这个掌握度来自哪些练习或行为？
```

这是 EduNova 区分普通 AI 聊天工具的重要能力。

### 12.5 模型 Provider 抽象

EduNova 不绑定单一大模型。后端通过统一 Provider 接口调用模型。

第一版支持 OpenAI-compatible 适配方式，并优先考虑：

```text
DeepSeek
通义千问
讯飞星火
Kimi
MiniMax
OpenAI-compatible
```

Provider 抽象至少包含：

```text
chat_completion
stream_chat_completion
embedding
model_list
health_check
```

前端设置页支持：

```text
选择模型供应商
填写用户自己的 API Key
测试连通性
选择默认生成模型
选择默认 embedding 模型
```

API Key 不写入日志。存储时第一版至少做脱敏展示，部署版应支持加密存储。

### 12.6 功能验收标准

核心验收标准：

| 功能 | 验收标准 |
| --- | --- |
| 注册登录 | 用户能注册、登录、退出，登录后访问学生 AI 学习空间 |
| 对话画像 | 至少生成 8 维画像，并能展示画像来源或更新时间 |
| 上传建课 | 上传一份 PPTX/PDF/DOCX/TXT 后能生成课程名、章节、知识点 |
| RAG 问答 | AI 回答必须显示至少一个引用来源；资料不足时提示依据不足 |
| 资源生成 | 对一个知识点生成至少 5 类资源 |
| Agent 轨迹 | 一次资源生成至少展示 4 个 Agent 步骤 |
| 学习路径 | 能根据画像和知识点生成阶段式路径与任务列表 |
| 练习评估 | 能作答、批改、展示掌握度和薄弱点 |
| 学习报告 | 包含掌握度、画像变化、下一步建议和证据说明 |
| Demo Mode | 无需手工配置复杂数据即可跑通主演示链路 |
| Docker Compose | 前端、后端、PostgreSQL、Redis 能一键启动 |
| 文档 | README、部署说明、架构说明、开源说明、答辩 QA 初版齐全 |

如果某项未达标，不能标记对应里程碑完成。

### 12.7 学习可视化与复盘增强

EduNova 第一版需要让“个性化”被直观看见，而不是只停留在文字说明。

第一版应实现的可视化：

| 能力 | 说明 |
| --- | --- |
| 学习能力雷达图 | 展示知识基础、理解能力、实践能力、抽象能力、学习节奏、专注程度、表达偏好、薄弱风险 |
| 知识点掌握地图 | 展示课程知识点及状态：未学习、学习中、已掌握、薄弱、推荐复习 |
| 学习路径时间线 | 将路径拆成可执行任务，展示当前阶段、今日任务、后续任务 |
| Agent 轨迹时间线 | 展示各智能体运行过程、耗时、审核结果 |

画像雷达图必须来自 `student_profiles.profile_json`，不能只做静态图。知识点掌握地图必须和 `learning_tasks`、`practice_answers`、`assessment_reports` 联动。

第一版数据结构需要支持：

```text
knowledge_mastery
weakness_review_queue
resource_quality_scores
learning_export_jobs
```

### 12.8 错题与薄弱点复习队列

学习评估不能只停留在报告，必须转化为下一步行动。

闭环流程：

```text
练习作答
  ↓
识别错题与薄弱知识点
  ↓
加入复习队列
  ↓
推荐讲解资源和新练习
  ↓
再次评估
  ↓
更新掌握度和画像
```

复习队列字段：

```text
user_id
course_id
knowledge_point_id
weakness_reason
priority
recommended_resource_ids
next_review_at
status
```

第一版至少要能展示：

```text
当前最需要复习的 3 个知识点
为什么被判定为薄弱
推荐复习资源
重新练习入口
```

### 12.9 资源质量评分

每个生成资源都要有质量解释，避免看起来像普通大模型输出。

资源评分维度：

| 维度 | 说明 |
| --- | --- |
| 资料匹配度 | 是否基于当前课程资料和引用 |
| 画像适配度 | 是否符合学生基础、偏好、节奏 |
| 事实可信度 | ReviewAgent 审核是否通过 |
| 难度适配度 | 是否过难或过浅 |
| 完整度 | 是否满足资源类型要求 |

评分结果保存到 `resource_quality_scores`，前端在 Studio 输出详情或资源摘要中显示：

```text
可信度 92
适配度 86
难度：适中
审核：通过
引用：3 条
```

评分不是为了追求绝对准确，而是为了让系统具备可解释的质量控制机制。

### 12.10 AI 学习档案导出

EduNova 应支持导出学生自己的学习档案，作为比赛展示和真实使用价值补充。

第一版目标格式：

```text
Markdown 导出
```

后期增强：

```text
PDF 导出
课程包导出
学习档案 ZIP
```

学习档案内容：

```text
学习画像摘要
画像变化记录
课程学习路径
生成过的核心资源
错题和薄弱点
掌握度变化
AI 学习报告
引用来源摘要
```

第一版可以先实现 Markdown 导出，PDF 导出作为 7月15日后文档与演示阶段的增强任务。

### 12.11 最终学习增强功能锁定

最后一轮功能增强聚焦真实学生使用场景和比赛辨识度，不再引入教师端、社区、移动端等偏离主线的功能。

第一版必须尽量落地的增强功能：

| 功能 | 说明 | 实现方式 |
| --- | --- | --- |
| 知识盲区溯源 | 不只指出错题，而是沿知识点依赖关系追溯到前置薄弱点 | 结合 `knowledge_mastery`、错题记录、知识点依赖图 |
| 期末冲刺模式 | 上传课件和历年题后，生成 3/7/14 天冲刺计划 | 复用上传建课、考点提炼、路径规划、复习队列 |
| 资料对比与考点提炼 | 对多份 PPT、讲义、试卷提取高频考点、重复重点和遗漏点 | CourseBuilderAgent + RetrieverAgent + AssessmentAgent |

第一版轻量实现的增强功能：

| 功能 | 说明 | 实现方式 |
| --- | --- | --- |
| 苏格拉底追问模式 | AI 不直接给答案，而是通过追问引导学生理解 | TutorAgent 增加 `socratic` 风格参数 |
| 学习会话回放 | 把一次学习过程记录成时间线，展示问题、资源、错题、Agent 行为 | 复用 `chat_messages`、`agent_run_logs`、`practice_sessions` |

后期路线图功能：

| 功能 | 说明 |
| --- | --- |
| 迷你互动实验 | 针对 AI 课程生成感知机分类、梯度下降、搜索算法等交互演示 |

期末冲刺模式的典型流程：

```text
上传课件/历年题/复习资料
  ↓
资料对比与考点提炼
  ↓
识别高频考点和薄弱点
  ↓
生成 3/7/14 天冲刺计划
  ↓
生成必刷题、易错提醒、复习资源
  ↓
每天练习与评估
  ↓
更新冲刺报告
```

知识盲区溯源示例：

```text
学生做错“反向传播梯度计算”
  ↓
系统定位当前知识点：反向传播
  ↓
沿依赖图回溯：链式法则 -> 偏导数 -> 损失函数 -> 梯度下降
  ↓
结合练习记录判断真正薄弱点：链式法则
  ↓
推荐补救资源和重练题
```

资料对比与考点提炼输出：

```text
高频考点
疑似考试重点
多份资料重复出现的概念
只在试卷中出现但课件讲得少的知识点
建议优先复习顺序
```

苏格拉底追问模式示例：

```text
学生：什么是梯度下降？
EduNova：你可以先猜一下，“梯度”在函数图像上代表什么方向？
学生回答后，系统再根据答案继续追问或纠偏。
```

学习会话回放需要展示：

```text
本次学习时长
提出的问题
检索到的资料来源
生成的资源
完成的练习
暴露的薄弱点
Agent 协作轨迹
下一步建议
```

这些功能共同强化 EduNova 的最终表达：

```text
它不仅能生成学习资源，还能找到为什么不会、该先补什么、怎么冲刺复习、学习过程如何复盘。
```

## 13. 两周里程碑

2026-07-01 到 2026-07-14 完成可运行系统；2026-07-15 到 2026-07-20 做测试、部署、文档、PPT、演示视频。

| 时间 | 目标 | 验收标准 |
| --- | --- | --- |
| Day 1 | 项目骨架 + 文档基线 | 前后端项目创建、Docker Compose 草案、README/架构文档初版 |
| Day 2 | 用户系统 + 学习空间框架 | 能注册登录，进入学生 AI 学习空间 |
| Day 3 | 课程与知识库模型 | 内置人工智能导论课程，课程/资料/知识点表可用 |
| Day 4 | 上传资料自动建课 v1 | 支持上传 PDF/PPTX/DOCX/TXT，能解析并生成课程结构 |
| Day 5 | RAG 检索 | 课程资料切片、向量化、问答能引用来源 |
| Day 6 | 对话式画像 | 6-8 维画像生成、保存、展示、更新 |
| Day 7 | 多智能体资源生成 | 生成 5 类资源，并记录 Agent 轨迹 |
| Day 8 | 学习路径规划 | 根据画像和知识点生成路径、任务、进度，并展示知识点掌握地图 |
| Day 9 | AI 辅导问答 | 基于课程资料、画像和 RAG 的个性化答疑 |
| Day 10 | 练习与学习评估 | 题目作答、批改、掌握度、复习队列、学习报告 |
| Day 11 | 防幻觉审核 + 引用溯源 | ReviewAgent、置信度、低依据提示 |
| Day 12 | 前端体验打磨 | 学习画布、AI 命令栏、Studio、路径图、证据层和 Agent 轨迹更像产品 |
| Day 13 | 部署与测试 | Docker Compose 跑通，核心链路测试通过，Demo Mode 可用 |
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

## 14. 风险控制

| 风险 | 处理 |
| --- | --- |
| 上传建课解析复杂 | 第一版做文本解析，OCR 后置 |
| 视频生成太重 | 第一版做视频脚本、分镜、PPT 大纲 |
| 多智能体慢 | 使用异步任务和进度展示 |
| 模型不稳定 | 提供 mock/fallback 演示模式 |
| UI 来不及 | 优先学生 AI 学习空间主链路 |
| 答辩压力大 | 同步维护 `docs/DEFENSE_QA.md` |
| API 成本高 | 用户级 Key、系统 Key 限额、Redis 限流 |
| 数据串用 | 用户私有数据按 `user_id` 隔离，课程内数据按 `user_id` 和 `course_id` 隔离 |

## 15. 设计结论

EduNova 第一版的正式基线是：

```text
面向学生个人的 AI 学习空间
+ 上传资料自动建课
+ 多智能体资源生成
+ RAG 引用溯源
+ 学习路径与评估闭环
+ 可部署、可开源、可答辩解释
```

当前实施计划、工程骨架、核心课程数据和 Phase 3 前端学习空间骨架已经推进完成。`/app` 已按 AI 对话主页、贴边可收起历史侧栏、侧栏账号入口、输入区资料库浮层入口、文件上传入口、较小输入框、发送后主页对话态、底部学习输入区、最近学习轻量列表、克制背景信号线和生成课程浮层落地；`/app/courses/:courseId` 已补课程空间静态壳子，承载课程内对话、知识画布、Studio、引用来源和 Agent 轨迹；`/app/library` 已调整为文件库式资料库，并支持从资料生成课程浮层；Studio、学习画像、AI 辅导、练习、报告和设置已补核心页面骨架；P3.7 已补主要按钮本地演示态反馈，防止前端出现明显空按钮。后续继续按该方向进入真实注册登录、上传建课、RAG、多智能体资源生成和学习闭环。
