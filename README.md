# EduNova

> 当前开发进度：Phase 48 已完成讯飞中文语音增强。主页和课程空间优先使用服务端讯飞语音听写与在线语音合成，失败时保留浏览器语音和键盘输入兜底。

视觉模型在“设置 → AI 服务”中有独立入口；国内默认使用讯飞开放平台原生图片理解，单独填写 APPID、APIKey 和 APISecret，经官方 WebSocket 协议调用。OpenAI-compatible 视觉服务仍可作为可选适配器；连接测试会用程序化小图验证完整结构化视觉合同，而非只检查是否返回文字。

部署端分别通过 `SYSTEM_MODEL_*`、`SYSTEM_GENERATION_*` 和 `SYSTEM_VISION_*` 提供回答、后台生成和图片理解兜底；向量与重排序也始终使用各自服务器配置。个人仅可配置回答模型，配置后同时覆盖自己的普通回答和后台生成，不接管图片理解或资料检索。

Phase 31 大型真实教材驱动的真用户闭环实战已完成：437 页整本 PDF 已通过普通用户界面完成上传、Docling 解析、目录确认、建课、RAG 问答、联网核实、路径、本节资源、练习、弱点、报告与 DOCX 导出。盲测发现的大教材截断、证据回答失真、资源/整节完成混淆、部分评分误显、路径降级、进度丢失和任务托盘遮挡等问题已按真实复现补回归并修复。

EduNova 是面向高校学生的 AI 个性化学习空间，目标是参加第十五届中国软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。

第一版聚焦学生个人学习闭环：

```text
对话建画像 -> 上传资料建课 -> RAG 检索引用 -> 多智能体生成资源
-> 个性化学习路径 -> AI 辅导 -> 练习评估 -> 学习报告
```

对话中的资源生成由模型理解语义：明确请求在课程空间自动创建任务，模糊需求先给出可确认建议，主页先选择目标课程；浏览器不再用关键词正则猜测资源类型。模型同时输出独立 `resource_topic`，服务端只在用户选定课程的真实知识点中校验并绑定该主题；匹配失败会诚实失败，不再默认使用课程首知识点。资源工坊仍支持用户手动选择七类资源。

## 当前阶段

当前已完成 **Phase 48 讯飞中文语音增强**。语音输入在浏览器采集后只向 EduNova 后端发送 16 kHz 单声道 PCM，由讯飞语音听写转成文字并回填输入框，不自动发送；回答朗读优先使用讯飞在线语音合成并支持暂停、继续和停止。服务端异常时自动降级到 Web Speech API，键盘输入始终可用。真实接口已经分别通过程序化中文录音与合成文本验证，未保存音频、转写原文或密钥。交付版 PPT、演示视频和提交包仍留到产品封盘后。

Phase 43 会剔除 Rerank 已完成时明显低相关的课程引用尾项，同时至少保留最佳证据；导图渲染会把常见 LaTeX 箭头规范化为可读符号，个性化理由不再出现重复句号。练习蓝图轮换课程事实，模型必须把占位干扰项改写为学科内可信误区；简答题禁止循环问法、锁定答案原文和空范围占位。精确答案泄漏只删除模型题干中的锁定答案片段并重新执行完整门禁，不用模板题冒充 AI 生成。

真实百炼练习验收以一次结构化调用在 28.2 秒内完成，推理 Token 为 0、无修订、五题均为 `model_generated`；路径和两类资源也通过真实内容阅读。跨学科泛化继续由计算机、数学、语言、人文和用户自建资料的固定自动化夹具守门，本轮没有为增加实测数量重复消耗外部调用。

Phase 42 修复了收起全局侧栏后“还没有历史对话”被挤成逐字竖排的问题，并让加载更多入口只在历史区展开时出现。资料库真正为空时现在明确引导使用右上角“上传”添加第一份资料；已有资料但搜索或类型筛选没有命中时，继续使用独立的筛选空态，避免把首次使用误写成搜索无结果。

本阶段定向回归 12 项、ESLint、编码检查和 production frontend build 通过；只重建 frontend 镜像。真实浏览器逐页审计未发现新的横向溢出、控制台错误或业务阻断，最终复核覆盖桌面收起侧栏和 390px 资料库，不重复运行大型教材、真实模型、隔离 Docker E2E或供应链扫描。

Phase 41 修复了“低分后再测通过，掌握度却仍按终身平均停在低位”的冲突。当前掌握度读取同一知识点最近一次完整练习会话的平均分；历史尝试继续进入报告趋势、证据数量和置信度。已攻克项在 `next_review_at` 前不再触发低分练习，到期后以明确的间隔复习重新进入闭环，报告同步展示起点、再测、提升和下次复习。

Phase 41 中量门禁通过后端 468 项、前端 246 项和离线评测 10 项。当前生产镜像的定向浏览器验收使用临时本地状态验证 3→98 分后课程掌握度为 98%、下一行动晋级为生成路径、已攻克项退出待处理及报告展示提升 95 分；桌面与 390px 无横向溢出。该状态仅用于界面回归，不重复计作模型实测，临时账号已删除。

Phase 40 将一次练习产生的结构化错因变成可执行复习单元。针对性练习生成会校验当前用户、课程、知识点和弱点状态，并把脱敏错因与缺失概念交给模型生成题面；再测结果写回起点分、最新分、提升值和尝试次数。未评分题不能关闭弱点，低于 80 分保持复习中，达到门槛后自动完成并安排后续复习日期。

Phase 40 阶段门禁通过后端 465 项、前端 246 项和离线评测 10 项，以及编码、Ruff、Alembic、OpenAPI、ESLint、production build 与 Compose。Docker 真页面以临时内置课程账号完成“3 分诊断 → 确认复习 → 98 分再测 → 自动完成”，并修复旧练习缓存污染再测入口和已完成弱点仍计入待处理数的问题；桌面与 390px 均无横向溢出，临时账号已级联删除。

Phase 39 修正了五类真用户问题：模型生成路径被误标为规则底稿；路径重排固定 30 秒导致慢模型失败；课程回答对证据中的定性事实支持关系判断不准；简答题范围含糊或直接泄露参考答案；练习修订丢失已通过字段且确定性干扰项带有计算机学科偏见。模型生成、课程证据、规则答案和严格质量门禁边界保持不变。

Phase 39 阶段门禁通过后端 462 项、前端 244 项和离线评测 10 项，以及编码、Ruff、Alembic、OpenAPI、ESLint、production build 与 Compose 配置检查。

Phase 38 新增项目内部 `ModelTaskProfile` 与 Provider 能力协商。百炼千问的路径、练习、评分、报告、画像和路由任务显式发送 `enable_thinking=false`，原生支持时使用 `response_format=json_object`；星火仅使用已验证的 `thinking.type`，未知 OpenAI-compatible 地址不接收猜测出来的私有参数。AIJob 只记录任务类型、修订次数、Token 和耗时聚合，不记录 Prompt、模型原文或用户资料。

Phase 38 收口通过后端 457 项、前端 244 项和离线评测 10 项，以及编码、Ruff、Alembic、OpenAPI、ESLint、production build 与 Compose。隔离 Docker E2E 通过服务健康、pgvector、代码执行隔离和 2 条 Playwright 用例；无模型环境明确失败且不保存模板路径。`agent-browser` 真实验证系统结构化连接为 `qwen3.7-plus · 2307 ms`，桌面与 390px 设置页均无横向溢出，临时账号已删除。

生成失败语义已改为诚实失败：路径失败保留旧路径，首次失败不创建模板路径；练习失败不创建会话；报告失败保留旧报告；文档、导图、代码、练习、PPT 和动画单类失败只显示未生成。课程事实、客观答案、统计、权限、引用和安全审核仍由确定性代码锁定。学习状态不变时复用现有有效模型路径；状态变化后才重新规划，避免为了表面差异重复付费。

Phase 37 将题目增强和报告叙事的安全自审并入同一次结构化响应，确定性规则继续独立锁定题型、答案、课程证据、统计数字和隐私。模型超时、输出非法或自审要求修订时，Graph 直接使用证据型题稿或确定性报告，不再追加第二次模型调用。练习题质量摘要同时记录真实生成模式、审核模式和使用的可信个性化因素。

Phase 36 新增 `/practice/sessions/generation-jobs` 与 `/reports/generation-jobs`。同用户同课程同工作流的活动任务会复用，任务完成结果只保存安全 ID、warnings 与 trace；失败或取消不会覆盖已有练习或报告。练习提交、简答重评和画像更新仍是需要立即返回业务结果的短时原子操作，不为表面统一强行异步化。

Phase 37 后端 447 项全量测试通过。Docker 真实 Provider 对照显示：旧练习任务因 3 次超时重试耗时 140.30 秒，最终代码下单次 50 秒尝试和安全 fallback 为 52.65 秒；旧报告因二次修订调用耗时 69.99 秒，最终代码下单次 40 秒尝试和安全 fallback 为 42.81 秒。两项都通过普通学生页面生成并显示可用结果，未把 fallback 冒充为模型增强成功。

Phase 33 阶段门禁通过后端 441 项、前端 241 项和离线 AI 评测 10 项，以及编码、Ruff、Alembic、OpenAPI、lint、production build 与 Compose。网络恢复后，AI Worker 已从空模型层成功下载并预装 Docling Layout 与 TableFormer 制品；模型下载层约 124 秒，紧接着的相同构建全部命中缓存并在约 3 秒内完成。另在 `--network none` 容器中使用程序化无版权两页 PDF 完成实际解析，页码、标题和正文均正确输出，证明新镜像可离线使用预装模型；外部模型仓库可用性仍作为首次构建环境风险保留。

本轮真实解析得到 437 页、约 98% 可读页、10 个顶层章、51 个目录条目和 479 个切片；建课生成 51 个知识点。三个临时账号共记录 140 次真实 Provider 尝试，未超过 180 次硬上限。两组内置课程画像的路径均为模型增强、无 fallback，同一“二叉树遍历”任务在教学策略与资源模态上产生可见差异。

Phase 31 完整工程门禁已通过后端 425 项、前端 238 项和离线评测 10 项，并通过编码、Ruff、Alembic、OpenAPI、lint、build 与 Compose。隔离 Docker E2E 的 2 条 Playwright 主链通过并自动清理容器、网络和卷；`agent-browser` 完成桌面与 390px 复核。三个临时账号、上传副本、导出、RQ 任务和派生数据已精确删除，原始 PDF 哈希未变化。本轮未提供新的真实性能样本，赛题就绪评测据实保留 `evidence_gap`。

Phase 25 的原生工具与模型主导编排继续保留：主页和课程空间由当前用户有效回答模型统一改写追问、判断联网和推理强度；星火 X2-Flash 与官方 OpenAI 优先使用厂商原生搜索，其他 OpenAI-compatible/DeepSeek 配置通过 LangChain `@tool` 与 LangGraph `ToolNode` 调用 EduNova 搜索服务。所有网页来源必须有可验证 URL，否则自动回退或明确降级。

同一会话按模型上下文预算裁剪真实消息；可控跨会话记忆默认开启，只保存当前用户的脱敏摘要、消息引用、向量和模型指纹，可在设置页关闭或清除派生索引，原始聊天记录不受影响。课程资料永远是课程问答第一证据，网页和历史对话只用于外部补充或上下文，不进入画像、弱点、掌握度、练习评分或教材证据。

当前十条真实生产 Graph 为 `MaterialIngestionGraph`、`ProfileGraph`、`CourseBuilderGraph`、`HomeTutorGraph`、`CourseTutorGraph`、`ResourceGenerationGraph`、`PathPlanningGraph`、`AssessmentGraph`、`ReportGraph` 和 `MaterialComparisonGraph`。学习档案导出明确保持确定性 Service + Redis/RQ Worker，不包装成 Agent；认证、设置、Dashboard 等非学习能力同样保持普通服务。

已经具备的主链路：

- 真实注册、登录、退出和受保护路由。
- 主页真实总览、分页历史搜索、会话级参考资料范围、同会话真实上下文、隐私可控的跨会话语义记忆、主页消息持久化和通用模型回答。
- 当前用户个人资料库上传、列表、详情和进度查询。
- TXT/Markdown 保留轻量解析，PDF/DOCX/PPTX 默认由 Docling 适配层输出既有结构合同，再通过 `CourseBuilderGraph` 生成带来源覆盖、学习目标、先修关系和安全审核的课程结构；`.doc`、`.ppt`、图片和扫描件不伪装解析。
- 课程知识点、知识切片、课程内历史和引用持久化。
- 课程空间真实模型 RAG 回答、SSE 流式输出、刷新恢复和双模式前端。
- `ProfileGraph` 管理真实 8 维学习画像、逐维可信度和证据事件；显式回答只接受模型验证后的白名单提案，隐式学习信号满足双来源与置信度门槛后才进入长期画像，模型失败时不再由正则猜测写入。
- 学习画像与课程学习状态的边界已经明确：用户级画像只保留一份，课程级弱点、路径和复习队列按课程聚合。
- `/courses/{course_id}/learning-state` 已实现课程级学习状态第一刀，可把课程问答弱点候选事件同步为 `pending` 待确认复习项，并在课程空间展示待复习弱点摘要。
- 课程级弱点复习项已支持确认、开始、完成和软忽略状态流转；软忽略项不在主列表展示，但继续参与去重。
- `/agents/traces/{trace_id}` 已实现当前用户 Agent 轨迹查询，响应包含 `workflow`、`artifact_type`、`artifact_id` 和白名单 metadata；课程空间“课堂协作轨迹”读取真实 trace 或真实空状态。
- `/resources/generate` 保留同步兼容；新入口 `/resources/generation-jobs` 通过 `AIJobRuntime` 和独立 `edunova_ai` 队列执行六类 v3 结构化资源。Planner 为每类资源制定教学策略、认知层级、案例方向、证据和学习结果，六个 Worker 按互补职责生成；ReviewAgent 同时审核意图、证据、完整内容和历史差异。课程资源支持版本族、版本切换、比较、换教法和优化当前版本，任何失败都不会覆盖旧成果。
- `/paths/generation-jobs` 是路径规划的新入口，复用 AIJob/RQ 提供排队、节点进度、刷新恢复、取消和失败重试；`/paths/generate` 仅保留旧客户端同步兼容。`PathPlanningGraph` 每次最多一次模型调用，练习评分先保存再异步重排，失败不覆盖原有效路径。
- `/courses/{course_id}/mastery-map` 只使用有效练习作答和课程弱点等明确证据；未评估知识点返回 `score=null`，不参与课程平均值。路径任务只表达学习进度，不再制造掌握度分数。
- `/practice/sessions/generation-jobs` 是当前练习生成入口，`/practice/sessions` 仅保留同步兼容；`/practice/sessions/{session_id}/answers` 继续同步返回评分闭环。题目引用、生成模式、Prompt 版本和质量摘要可追溯，客观分数始终由规则决定。
- `/reports/generation-jobs` 是当前报告生成入口，`/reports/generate` 仅保留同步兼容；`ReportGraph` 聚合最近 5 次练习、掌握度、弱点、路径和资源，模型只生成叙事和建议，数字矛盾经一次定向修订仍不通过时任务失败并保留旧报告。
- `/materials/compare` 已由 `MaterialComparisonGraph` 接管；每次对比保存不可变版本，可恢复最近结果、追溯真实资料分块和审核轨迹。资料对比是资料库内的独立辅助工具，不会隐式修改学习路径或练习。
- AI 辅导直接在 `/app/courses/:courseId` 课程空间内完成；已移除无独立能力的中转页，旧 `/app/tutor` 地址会回到学习主页。
- 个人模型设置只提供回答模型。普通主页/课程对话使用个人回答模型；资源、路径、练习和报告也随之覆盖。未配置个人模型时，服务器 X2-Flash 负责回答，服务器千问负责后台生成与图片理解，向量和重排序继续使用服务器托管服务。
- 设置中心支持回答、向量与重排序独立验证，并提供显式向量重建任务；账号体系使用独立账号和昵称，登录账号统一小写且创建后不可修改，账号区支持修改昵称和密码，密码更新后所有旧 JWT 立即失效；隐私区可管理跨会话记忆并说明原始聊天与派生索引的区别。
- 模型调用采用任务级有界尝试，不在故障后自动转发到另一 Provider；语义路由等内部判断可保守降级，学生可见生成成果则明确失败并保留旧有效版本。
- `model_call_runs` 只记录模型名、状态、尝试次数、耗时和安全错误分类，Agent trace 可查看聚合调用摘要，不保存 Prompt 或回答正文。
- 讯飞原生 2560 维 Embedding、百炼/硅基 OpenAI-compatible Embeddings、动态 pgvector 与可选 Rerank 已接入；主页资料与课程 RAG 使用关键词 Top 30、向量 Top 30、RRF Top 20、重排序后 Top 5，任一外部能力不可用时按层降级。
- Docker Compose 新增仅内部网络可访问的 `code-verifier`。生成代码在非 root、只读文件系统、无外网和资源限制下由 Pyodide 独立 Worker 运行，只有安全策略、运行结果和预期输出全部一致时才允许保存。
- Phase 12.2 已补交付基线文档、测试报告、用户指南、开源说明、答辩问答、AI 辅助开发说明和 MIT 许可证。

主页回答已由 `HomeTutorGraph` 接管，`SemanticDecisionService` 使用当前用户有效模型判断资料推荐、时效核实、外部来源需求与推理强度，并通过 SSE 展示状态、真实来源、增量 Markdown、Review/Repair 和九节点安全 trace；未配置搜索 Key 或语义模型失败时 warning 只进入来源/轨迹区，不伪造网页来源。主页和课程空间的语音输入、朗读优先使用服务端讯飞 IAT/TTS，失败时回退浏览器 Web Speech；录音仅用于当次转写且不持久化。`CourseTutorGraph` 同样先做结构化语义决策再检索课程资料；课程资料仍优先，网页只能作为外部补充。只有模型高置信识别出学生明确困难、偏好、目标或基础表达时才产生画像候选，普通提问和“为什么”不会自动成为薄弱点。

主页侧栏通过 `/tutor/sessions/history` 首批读取 30 条未归档主页会话并按需继续加载，服务端搜索覆盖标题和消息正文。主页会话保存最多 10 份已解析参考资料；确认后刷新或通过 `session_id` 恢复会话时自动恢复，建课资料选择使用独立状态，不会反向改写对话资料范围。

还没有进入的能力：

- OCR、图片题目识别、旧版 Office 和扫描件解析。
- OCR、图片题目识别之外的多模态向量检索。
- 个人全局资源生成入口；课程级结构化资源已支持后台任务与不可覆盖的历史版本，个人全局资源仍未接入。
- 学习档案导出的 Agent 化；当前确定性 Service + RQ 已满足业务需要，不列为默认开发目标。

详细状态见 [docs/STATUS.md](docs/STATUS.md)，后续任务看 [docs/PROJECT_BOARD.md](docs/PROJECT_BOARD.md)。

## 文档入口

| 文档 | 说明 |
| --- | --- |
| [当前状态](docs/STATUS.md) | 当前完成到哪里、能用什么、还缺什么 |
| [项目看板](docs/PROJECT_BOARD.md) | 下一步优先级、里程碑和风险 |
| [赛题原文](docs/软件杯A3赛题.txt) | A3 赛题要求 |
| [赛题逐句矩阵](docs/CONTEST_REQUIREMENT_MATRIX.md) | 逐条区分已实现、缺实证、待确认与交付未开始 |
| [仓库规则](AGENTS.md) | 编码、文档同步、Git、密钥和完成定义 |
| [需求规格](docs/REQUIREMENTS.md) | 功能范围和验收标准 |
| [架构设计](docs/ARCHITECTURE.md) | 前后端、后端分层、RAG、模型和部署架构 |
| [API 设计](docs/API.md) | 前后端接口约定 |
| [数据库设计](docs/DATABASE_DESIGN.md) | 数据表、字段和关系 |
| [RAG 检索设计](docs/RAG_DESIGN.md) | 课程知识库、Embedding fallback、混合召回和引用字段 |
| [前端与交互设计基线](docs/UI_UX_DESIGN.md) | 页面结构、视觉方向、交互规则和验收标准 |
| [前端路由设计](docs/FRONTEND_ROUTING_DESIGN.md) | 登录、注册、应用路由、课程空间和路由保护 |
| [课程空间双模式设计](docs/COURSE_SPACE_DESIGN.md) | 课程问答模式、学习模式、引用层和后续改造顺序 |
| [测试计划](docs/TEST_PLAN.md) | 测试范围、自动化验证和浏览器验收 |
| [安全基线](docs/SECURITY.md) | 账号、密钥、上传资料、RAG、日志和权限安全 |
| [隐私说明](docs/PRIVACY.md) | 跨会话记忆、原始聊天、派生索引和联网数据边界 |
| [部署说明](docs/DEPLOYMENT.md) | 本地开发、Docker Compose、环境变量和迁移 |
| [风险登记册](docs/RISK_REGISTER.md) | 项目风险、触发信号和应对策略 |
| [Agent 设计说明](docs/AGENT_DESIGN.md) | 多智能体角色、trace 白名单和失败恢复 |
| [开发指南](docs/DEVELOPMENT_GUIDE.md) | 本地开发、分支、测试、文档同步和浏览器验收 |
| [开源说明](docs/OPEN_SOURCE_NOTICE.md) | MIT 协议、第三方依赖、密钥和隐私边界 |
| [答辩问答](docs/DEFENSE_QA.md) | 赛题、RAG、多智能体、安全、部署和后续打磨问答 |
| [开发报告](docs/DEVELOPMENT_REPORT.md) | 系统设计、阶段成果、核心创新和当前限制 |
| [测试报告](docs/TEST_REPORT.md) | 自动化测试、Docker、浏览器验收和证据索引 |
| [用户指南](docs/USER_GUIDE.md) | 学生端使用流程 |
| [AI 辅助开发说明](docs/AI_CODING_USAGE.md) | AI Coding 使用边界、人工审查和隐私规则 |
| [Phase 12.2 验收证据](docs/evidence/PHASE_12_2_ACCEPTANCE.md) | 当前交付基线的验证命令和浏览器验收记录 |
| [产品设计](docs/superpowers/specs/2026-07-01-edunova-product-design.md) | 产品定位和设计原始稿 |
| [实施计划](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md) | 阶段路线和实现计划原始稿 |
| [中文阅读版](docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md) | 实施计划中文导读 |

## 第一版完整目标

- 学生注册登录。
- 对话式 8 维学习画像。
- 可选的《数据结构与算法》内置课程：8 个理论章节、56 个知识点、184 个证据切片和 16 个 Python 实验。
- 上传资料自动建课。
- RAG 检索和引用展示。
- 多智能体协作生成学习资源。
- 个性化学习路径。
- AI 辅导和苏格拉底追问。
- 练习评估、掌握度地图和薄弱点复习队列。
- 资料对比与考点提炼。
- Markdown/PDF/DOCX 学习档案异步导出，旧 Markdown 同步接口保留兼容。
- 快速体验可在注册页主动选择数据结构与算法内置课程；新用户默认空白开始，不创建共享 demo 账号。
- Docker Compose 部署。

当前代码已经具备第一版主学习闭环和交付基线，但仍不是完整商业产品。不要把“第一版目标”误读成 OCR、扫描件解析、旧版 Office 格式解析、教师端和完整 E2E 都已经完成。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、Tailwind CSS、React Router、Zustand、React Query |
| 后端 | FastAPI、SQLAlchemy、Alembic、Pydantic、PyJWT、bcrypt |
| 数据 | PostgreSQL、pgvector、Redis、本地文件存储 |
| AI | Spark X2-Flash / OpenAI-compatible Chat、讯飞与兼容 Embeddings、可选 Rerank、动态 pgvector、SSE 与关键词 fallback |
| 工程 | Docker Compose、Nginx、pytest、Vitest、Playwright、ESLint、ruff、PowerShell 检查脚本 |

## 编码规则

- 所有文本文件使用 UTF-8 无 BOM。
- 禁止 UTF-16、GBK。
- 中文直接写入，不使用 `\uXXXX`。
- 不提交真实 `.env`、API Key、JWT、上传文件和缓存。
- 涉及接口、数据库、架构、测试、部署或安全变化时必须同步文档。

## 本地后端验证

创建虚拟环境并安装依赖：

```powershell
py -3.12 -m venv .venv
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:PIP_PROGRESS_BAR='off'
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

运行完整检查：

```powershell
.\scripts\test.ps1
```

启动后端：

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 本地前端验证

安装依赖后运行：

```powershell
cd frontend
pnpm install
pnpm lint
pnpm test
pnpm build
cd ..
```

启动开发服务器：

```powershell
cd frontend
pnpm dev
```

默认访问：

```text
http://127.0.0.1:5173
```

前端开发服务器已配置 `/api` 代理，默认转发到 `http://127.0.0.1:8000`。
本地验收真实登录、上传、建课和课程问答时，需要同时启动后端。

## Docker Compose 验证

当前 Compose 草案包含：

- PostgreSQL + pgvector。
- Redis。
- FastAPI backend。
- React 前端生产静态服务。
- Nginx 统一入口，默认宿主机端口 `8080`。

校验配置：

```powershell
docker compose config
```

启动并构建：

```powershell
docker compose up --build -d
```

Docker 构建上下文会忽略本地 `node_modules`、`dist`、`.vite`、`output` 等运行产物，避免把本机依赖复制进 Linux 镜像。

停止：

```powershell
docker compose down
```

统一入口：

```text
http://127.0.0.1:8080
http://127.0.0.1:8080/health
http://127.0.0.1:8080/api/health
```

## 数据库迁移

当前 Alembic 配置文件位于 `alembic.ini`，迁移目录位于 `backend/migrations`。

启动 PostgreSQL 后运行迁移：

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic upgrade head
```

如果已经启动完整 Docker 栈，也可以直接在后端容器中执行迁移：

```powershell
docker compose exec -T backend python -m alembic upgrade head
```

同步内置课程包并替换旧内置课：

```powershell
.\.venv\Scripts\python -m backend.app.cli sync-builtin-courses
```

完整 Docker 栈中可以改用：

```powershell
docker compose exec -T backend python -m backend.app.cli sync-builtin-courses
```

Docker 后端会在迁移完成后自动执行该同步。课程包包含 9 份仅在课程内部可见的系统来源、56 个知识点、184 个切片和 16 个 Python 实验；不会在个人资料库创建衍生文件。课程正文和实验均为重新组织的原创表达，仓库不包含参考教材 PDF、扫描页、插图或教材代码。课程包另有逐知识点教学指引、32 条关键词 RAG 基准和 16 组可执行边界验证，详见 `docs/BUILTIN_COURSE_QUALITY.md`。

## 资料解析与智能建课

用户上传的 TXT、Markdown、PDF、DOCX 和 PPTX 会进入后台 `MaterialIngestionGraph`，依次完成页面提取、版面清理、目录识别、章节内切片、质量门禁和持久化。资料库始终只展示原文件；目录候选、页码、切片和解析诊断仅作为系统内部数据。

解析成功后资料进入“待确认”状态。用户可以在资料详情中检查目录、页码与真实切片，排除无关章节、改名、合并或拆分边界，再确认结构。只有目录已确认且质量通过的资料才能进入 `CourseBuilderGraph`。建课按章节并行分析，知识点必须绑定真实切片，并通过章节覆盖、证据完整、标题去重和先修无环等门禁后才会落库。
