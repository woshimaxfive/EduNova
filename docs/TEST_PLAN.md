# EduNova 测试计划

日期：2026-07-01

## 1. 测试目标

EduNova 的测试目标不是只证明代码能运行，而是证明系统满足赛题要求、适合比赛演示、能够后续开源部署，并且关键 AI 输出具有可解释性和可信度。

本文档是全项目测试计划。除“当前自动化验证入口”一节外，其他章节描述的是第一版最终应覆盖的测试范围，不代表当前 Phase 2C 已经全部实现。当前 Phase 2C 已验收 FastAPI 最小骨架、`/api/health`、pytest、ruff、编码检查、Docker Compose 配置、PostgreSQL、Redis、backend 三服务真实启动健康检查、SQLAlchemy 数据库入口、Alembic 迁移环境、pgvector 扩展迁移、第一批核心业务表迁移和人工智能导论内置课程包导入。

测试需要覆盖以下问题：

1. 学生是否能完整走通学习闭环。
2. 上传资料是否能正确解析并生成课程。
3. 多智能体是否真实参与资源生成过程。
4. 生成资源是否至少包含 5 类，并能体现个性化。
5. RAG 回答和资源生成是否有引用来源。
6. ReviewAgent 是否能给出审核状态、置信度和风险提示。
7. 学习路径、练习评估、掌握度和复习队列是否能联动。
8. Demo Mode 是否能在模型不稳定时保证演示不中断。
9. Docker Compose 是否能一键启动核心服务。
10. 所有文件是否满足 UTF-8 无 BOM、中文不转义、无密钥泄露的要求。

## 2. 测试范围

### 2.1 必测范围

| 模块 | 必测内容 |
| --- | --- |
| 用户系统 | 注册、登录、退出、鉴权、访问保护 |
| AI 学习空间 | 顶部轻导航、学习画布、AI 命令栏、Studio 输出区、证据层入口 |
| 对话式画像 | 8 维画像生成、画像更新、画像事件记录 |
| 课程系统 | 内置人工智能导论课程、课程列表、课程详情 |
| 上传建课 | PDF、PPTX、DOCX、Markdown、TXT 解析与课程生成 |
| RAG 检索 | 切片、向量化、检索、引用来源展示 |
| 多智能体 | Agent 流程、trace_id、agent_run_logs、失败记录 |
| 资源生成 | 讲解文档、思维导图、练习题、代码案例、PPT 大纲或视频脚本 |
| 学习路径 | 任务排序、进度更新、推荐理由 |
| 掌握度地图 | 知识点状态、薄弱点、复习队列 |
| AI 辅导 | 课程内问答、引用来源、资料不足提示、苏格拉底模式 |
| 练习评估 | 出题、作答、批改、错题讲解、报告生成 |
| 期末冲刺 | 3/7/14 天计划、高频考点、必刷题、易错提醒 |
| 资料对比 | 多资料重复重点、试卷独有考点、优先复习顺序 |
| 导出 | Markdown 学习档案导出 |
| Demo Mode | 演示账号、演示数据、fallback 标记、重置能力 |
| 部署 | Docker Compose 启动、环境变量、Nginx 入口 |
| 文档 | README、部署说明、开发说明、测试说明、开源说明、答辩问答 |
| 前端体验 | `docs/UI_UX_DESIGN.md` 中的布局、状态、动效和响应式约束 |
| 前端入口 | `docs/FRONTEND_ROUTING_DESIGN.md` 中的登录、注册、Demo、首次进入和路由保护 |

### 2.2 暂不作为第一版必测范围

| 能力 | 原因 |
| --- | --- |
| 扫描版 PDF OCR | 第一版暂不支持 |
| 图片题目识别 | 第一版暂不支持 |
| 视频文件解析 | 第一版暂不支持 |
| 真实教学视频生成 | 第一版使用视频脚本或 PPT 大纲替代 |
| 完整教师端 | 第一版学生端优先 |
| 家长端、支付、移动端 | 不属于第一版主线 |

## 3. 测试分层

EduNova 采用 7 层测试策略。

### 3.1 静态检查

目标：保证代码和文档基础质量。

检查项：

- 文件编码必须是 UTF-8 无 BOM。
- 禁止 UTF-16、GBK。
- 中文直接写入，禁止 `\uXXXX`。
- 禁止提交真实 `.env` 和 API Key。
- 后端代码通过 ruff。
- 前端代码通过 lint。
- TypeScript 类型检查通过。

计划命令：

```powershell
.\scripts\verify_encoding.ps1
.\.venv\Scripts\python -m ruff check backend
```

前端创建后再启用：

```powershell
cd frontend
pnpm lint
pnpm build
cd ..
```

### 3.2 后端单元测试

目标：验证服务层、解析器、Agent 节点、RAG 工具和评分逻辑。

重点测试：

- 密码加密与 JWT。
- 文档解析。
- 文本切片。
- 课程结构抽取 fallback。
- Provider 抽象。
- RAG 检索。
- Agent 日志记录。
- 资源质量评分。
- 掌握度计算。
- 薄弱点追溯。
- 学习报告生成。

计划命令：

```powershell
.\.venv\Scripts\python -m pytest backend\tests
```

### 3.3 后端接口测试

目标：验证 API 输入输出、权限控制和异常处理。

重点接口：

| 接口 | 测试点 |
| --- | --- |
| `/auth/register` | 注册成功、重复邮箱、弱密码 |
| `/auth/login` | 登录成功、密码错误 |
| `/auth/me` | 有 token 成功，无 token 失败 |
| `/profiles/chat` | 画像生成、画像事件写入 |
| `/materials/upload` | 文件上传、格式限制、进度状态 |
| `/courses/from-materials` | 课程生成、知识点生成 |
| `/rag/search` | 检索结果、引用字段 |
| `/resources/generate` | 5 类资源、trace_id、审核状态 |
| `/paths/generate` | 学习路径、任务列表、推荐理由 |
| `/tutor/sessions` | 会话创建、消息记录 |
| `/practice/sessions` | 出题、提交答案、批改 |
| `/reports/generate` | 学习报告、证据来源 |
| `/demo/reset` | 演示数据重置 |

### 3.4 前端组件与页面测试

目标：验证核心页面能正确渲染和响应用户操作。

重点页面：

- 登录页
- 注册页
- Demo 入口页或 Demo 按钮流程
- 学习空间
- 资料库
- Studio
- 对话画像页
- 学习路径页
- AI 辅导页
- 练习评估页
- 学习报告页
- 设置页

重点 UI 结构：

- 顶部轻导航。
- 中央学习画布。
- 底部 AI 命令栏。
- 资料源簇。
- Studio Dock。
- 可滑出证据层。
- Agent 轨迹时间线。
- 首次进入引导。
- 受保护路由跳转。

计划命令：

```powershell
cd frontend
pnpm test
pnpm build
cd ..
```

### 3.5 浏览器端到端测试

目标：模拟真实学生完整使用流程。

主流程：

```text
打开登录页
-> 注册或使用演示账号登录
-> 进入 AI 学习空间
-> 完成对话式画像
-> 选择人工智能导论课程
-> 生成 5 类资源
-> 查看 Agent 轨迹和引用来源
-> 生成学习路径
-> 进入 AI 辅导问答
-> 完成练习
-> 查看学习报告
-> 导出 Markdown 学习档案
```

上传建课流程：

```text
登录
-> 上传 Markdown 或 PPTX 样例资料
-> 查看解析进度
-> 生成课程概览
-> 查看章节和知识点
-> 对新课程生成资源和路径
```

期末冲刺流程：

```text
登录
-> 上传课件和样例试题
-> 执行资料对比
-> 生成 3/7/14 天冲刺计划
-> 查看高频考点、必刷题和易错提醒
```

计划命令：

```powershell
cd frontend
pnpm exec playwright test
cd ..
```

## 4. AI 能力专项测试

AI 能力不能只看“有没有输出”，还要看输出是否可用、可信、可解释。

### 4.1 对话画像测试

测试输入：

```text
我是计算机专业大二学生，机器学习刚入门，数学基础一般，想在期末前快速掌握神经网络和反向传播。我喜欢通过案例和图解学习，纯公式会比较吃力。
```

预期结果：

- 能抽取专业背景。
- 能识别知识基础。
- 能识别学习目标。
- 能识别学习偏好。
- 能识别薄弱点。
- 能生成画像事件。
- 画像变化有理由和证据。

### 4.2 RAG 引用测试

测试问题：

```text
什么是启发式搜索？它和盲目搜索有什么区别？
```

预期结果：

- 回答引用人工智能导论资料。
- 至少显示 1 条引用来源。
- 引用来源包含章节、材料或片段信息。
- 如果资料不足，明确提示依据不足。

### 4.3 多智能体资源生成测试

测试任务：

```text
针对“反向传播”生成个性化学习资源，学生数学基础一般，偏好案例和图解。
```

预期结果：

- 生成讲解文档。
- 生成思维导图。
- 生成练习题。
- 生成代码实操案例。
- 生成 PPT 大纲或视频脚本。
- Agent 轨迹至少包含画像、检索、诊断、资源、审核 5 类步骤中的 4 类。
- 每个资源有引用、审核状态和可信度。

### 4.4 防幻觉测试

测试方法：

- 提问课程资料没有覆盖的问题。
- 上传一份很短资料，让系统生成资源。
- 输入带有提示词注入倾向的内容，例如要求系统忽略引用来源。

预期结果：

- 系统不应把没有依据的内容伪装成课程资料结论。
- 低依据内容应标记为外部扩展或需要复核。
- ReviewAgent 应给出风险提示。
- API Key、系统提示词、内部配置不应出现在回答中。

### 4.5 个性化一致性测试

测试方法：

用两个不同画像的学生请求同一知识点资源：

```text
学生 A：数学基础弱，喜欢案例
学生 B：数学基础强，喜欢公式推导
```

预期结果：

- 学生 A 的讲解更偏案例、类比和步骤拆解。
- 学生 B 的讲解可包含更正式的公式和推导。
- 两者引用来源可以相同，但表达和任务难度应不同。

## 5. 数据与隐私测试

### 5.1 多用户隔离

测试目标：

- 用户 A 不能看到用户 B 的课程。
- 用户 A 不能看到用户 B 的画像。
- 用户 A 不能访问用户 B 的资源、报告和对话。

测试方式：

- 创建两个账号。
- 分别上传资料、生成资源。
- 用错误用户 token 访问对方数据。

预期结果：

- 返回 403 或 404。
- 不泄露对方数据标题、内容、路径。

### 5.2 API Key 安全

测试目标：

- 用户 API Key 不进入日志。
- 前端只展示脱敏 Key。
- `.env` 不进入 Git。

测试方式：

- 设置一个测试 Key。
- 搜索日志和仓库。

计划命令：

```powershell
rg -n "sk-|ghp_|api[_-]?key|secret" .
git status --short --untracked-files=all
```

预期结果：

- 只允许 `.env.example`、测试说明或安全说明中出现假示例。
- 不允许出现真实密钥。

## 6. 性能与体验测试

第一版不追求极限性能，但必须满足比赛演示和日常学习体验。

| 场景 | 目标 |
| --- | --- |
| 登录 | 2 秒内返回 |
| 学习空间加载 | 3 秒内首屏可见 |
| RAG 检索 | 3 秒内返回引用片段 |
| 普通 AI 问答 | 支持流式输出，避免长时间白屏 |
| 资源生成 | 有进度状态或 Agent 轨迹 |
| 上传建课 | 有明确阶段进度 |
| Demo Mode | 关键流程稳定可复现 |

体验检查：

- 登录页不能像后台系统登录框，必须体现 EduNova AI 学习空间气质。
- 注册页不做复杂画像问卷，注册后进入首次进入引导。
- Demo 体验入口清晰，并具备初始化中、成功、失败状态。
- 未登录访问 `/app/*` 必须跳 `/login`。
- Token 失效后清理登录态并跳回 `/login`。
- 页面不能出现明显重叠。
- 按钮文字不能溢出。
- 移动端宽度下核心内容可读。
- 长任务不能无提示等待。
- 错误信息应告诉用户下一步怎么做。
- 首屏不能退化成固定左侧后台菜单或卡片堆。
- 背景动效不能影响文字可读性。
- 证据层默认弱化，但引用、Agent 轨迹和 ReviewAgent 结论必须可打开查看。

## 7. 部署测试

目标：证明项目能被别人拉下来运行，而不是只在本机能跑。

测试步骤：

```powershell
copy .env.example .env
docker compose config
docker compose up --build
```

预期结果：

- PostgreSQL 正常启动。
- Redis 正常启动。
- 后端健康检查通过。
- 前端页面可访问。
- Nginx 入口可访问。
- Demo Mode 可初始化。

部署验收地址：

```text
http://localhost
http://localhost/api/health
```

## 8. 回归测试

每次完成一个核心模块后，至少执行：

```powershell
.\scripts\verify_encoding.ps1
.\.venv\Scripts\python -m pytest backend\tests
cd frontend
pnpm test
pnpm build
cd ..
```

每次准备演示前，执行完整浏览器验收流程。

## 9. 测试数据计划

### 9.1 内置课程数据

课程：人工智能导论

知识点至少包括：

- 人工智能概述
- 搜索问题与状态空间
- 启发式搜索
- 知识表示
- 机器学习基础
- 监督学习
- 神经网络
- 反向传播
- 自然语言处理
- 计算机视觉
- 智能体与多智能体
- AI 伦理与安全

### 9.2 上传样例资料

准备以下样例：

| 文件 | 用途 |
| --- | --- |
| `sample_ai_notes.md` | 快速测试 Markdown 建课 |
| `sample_ai_notes.txt` | 测试纯文本解析 |
| `sample_ai_slides.pptx` | 测试 PPTX 解析 |
| `sample_ai_chapter.pdf` | 测试 PDF 解析 |
| `sample_ai_review.docx` | 测试 DOCX 解析 |
| `sample_exam_questions.md` | 测试期末冲刺和资料对比 |

### 9.3 演示账号

```text
邮箱：demo@edunova.local
密码：Demo123456
名称：演示学生
```

## 10. 缺陷分级

| 等级 | 定义 | 示例 |
| --- | --- | --- |
| P0 | 阻断提交或演示 | 系统启动失败、登录失败、主链路无法走通 |
| P1 | 严重影响核心功能 | 无法生成 5 类资源、RAG 无引用、上传建课失败 |
| P2 | 明显影响体验或答辩 | Agent 轨迹缺失、报告解释不足、页面错位 |
| P3 | 可延后优化 | 文案不够精炼、局部样式不够漂亮、非核心页面小问题 |

提交前 P0、P1 必须清零。P2 尽量清零，未清零必须记录在测试说明书中。

## 11. 阶段验收标准

| 阶段 | 验收标准 |
| --- | --- |
| Phase 0 | 编码检查脚本可运行，赛题和计划纳入 Git |
| Phase 1A | FastAPI 最小骨架、后端健康检查、pytest、ruff、编码检查通过 |
| Phase 1B | Docker Compose 草案、PostgreSQL、Redis 和后端服务健康检查通过 |
| Phase 2A | 数据库配置、SQLAlchemy、Alembic 和 pgvector 扩展迁移通过 |
| Phase 2B | 用户、课程、资料、知识点和知识切片核心表创建成功 |
| Phase 2C | 人工智能导论课程可导入且重复执行不产生重复课程 |
| Phase 3 | 前端学习空间壳子可打开，符合 `docs/UI_UX_DESIGN.md` 和 `docs/FRONTEND_ROUTING_DESIGN.md`，构建通过 |
| Phase 4 | 注册登录闭环通过 |
| Phase 5 | 上传资料能生成课程结构 |
| Phase 6 | RAG 检索返回引用 |
| Phase 7 | 对话生成 8 维画像和画像事件 |
| Phase 8 | 生成 5 类资源并显示 Agent 轨迹 |
| Phase 9 | 学习路径、掌握度图、复习队列可用 |
| Phase 10 | AI 辅导、练习、评估报告闭环通过 |
| Phase 11 | 期末冲刺和资料对比可演示 |
| Phase 12 | Demo Mode 和导出可用，文档初版齐全 |
| Phase 13 | 自动化测试、Docker、浏览器验收通过 |
| Phase 14 | PPT、视频、提交包准备完成 |

## 12. 提交前最终检查

提交比赛材料前必须完成：

```powershell
.\scripts\test.ps1
docker compose config
docker compose up --build
.\scripts\verify_encoding.ps1
git status --short --untracked-files=all
```

人工检查：

- README 能指导别人启动项目。
- `.env.example` 不含真实密钥。
- Docker Compose 可复现启动。
- 演示视频 7 分钟以内。
- PPT 逻辑清晰。
- 开源项目引用和协议说明完整。
- AI Coding 工具使用说明完整。
- 测试说明书包含测试范围、测试数据、测试结果和已知问题。

## 13. 当前自动化验证入口

Phase 1A 起，仓库提供统一验证脚本：

```powershell
.\scripts\test.ps1
```

当前已覆盖：

- UTF-8 无 BOM 与中文不转义检查。
- 后端 pytest 测试。
- 数据库配置、SQLAlchemy engine、Alembic metadata 和 pgvector 首迁移测试。
- 核心业务模型、约束、JSONB 字段、向量字段和第二条迁移测试。
- 人工智能导论课程包结构、对象图映射和导入幂等性测试。
- 后端 ruff 检查。
- Alembic revision head 解析检查。
- Docker Compose 配置校验。
- 当前未创建前端时自动跳过前端检查。
- 当前未接入核心业务表、前端和 AI/RAG；这些检查将在后续阶段加入。

统一验证脚本是日常轻量门禁，不会自动启动 Docker 容器。

后端健康检查测试：

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_health.py
```

当前健康检查响应：

```json
{"status":"ok","service":"edunova-api"}
```

Docker Compose 阶段验收命令：

```powershell
docker compose config
docker compose up --build -d postgres redis backend
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m backend.app.cli seed-ai-intro
docker compose ps
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get
docker compose down
```

## 14. 测试结论标准

只有同时满足以下条件，才能认为 EduNova 第一版测试通过：

1. 核心学生学习闭环可以在浏览器中完整走通。
2. 至少一门人工智能导论课程可正常学习。
3. 至少一份用户上传资料可以自动生成课程。
4. 至少 5 类个性化资源生成成功。
5. AI 输出包含引用来源、审核状态和 Agent 轨迹。
6. 练习评估能影响掌握度、薄弱点和学习报告。
7. Demo Mode 可稳定演示。
8. Docker Compose 可启动系统。
9. P0、P1 缺陷清零。
10. 文档、PPT、视频和提交包齐全。
