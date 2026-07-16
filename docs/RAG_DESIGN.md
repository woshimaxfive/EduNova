# EduNova RAG 检索与引用设计

## 1. 当前目标

EduNova 的主页资料问答与课程问答共用同一套检索底座，但保持不同证据边界：

- 主页只检索当前用户在该会话中确认选择的资料，并允许模型使用通用知识。
- 课程空间优先检索当前用户课程内的知识切片；只有时效问题、明确外部核实，或已确认课程相关但没有课程命中时才补充网页来源。
- 联网搜索由 `HomeTutorGraph.web_search` 和 `CourseTutorGraph.web_search` 统一编排：星火 X2-Flash/官方 OpenAI 原生搜索优先，无可验证来源时回退 Tavily-compatible 服务；DeepSeek 与普通兼容接口使用 EduNova `search_web` 工具。
- 引用只返回安全短片段、来源、章节、页码和检索状态，不返回完整资料、向量或模型输入。

## 2. 向量能力

向量连接与回答连接独立保存、独立测试、独立选择默认用途。当前支持：

| Provider | 协议 | 默认模型 | 维度 |
| --- | --- | --- | --- |
| 讯飞星火 | 原生签名 HTTP | LLM Embedding | 固定 2560 |
| 阿里云百炼 | OpenAI-compatible `/embeddings` | `text-embedding-v4` | 预设 1024，可按实际响应识别 |
| 硅基流动 | OpenAI-compatible `/embeddings` | `BAAI/bge-m3` | 1024 |
| 自定义服务 | OpenAI-compatible `/embeddings` | 用户填写 | 由连接测试和实际响应识别 |

讯飞资料使用 `domain=para`，问题使用 `domain=query`。单次输入超过 2KB 时按 UTF-8 字节边界安全拆分，分段向量做均值池化和归一化，不截断中文正文。

`knowledge_chunks.embedding` 和 `material_chunks.embedding` 使用无固定维度的 pgvector `vector`。每条向量同时记录：

- `embedding_provider`
- `embedding_model`
- `embedding_dimension`
- `embedding_profile_hash`
- `embedding_updated_at`

检索必须匹配用户、课程或资料、Provider、模型、维度和配置指纹。旧 1536 维向量保留为 legacy 数据，但缺少新配置指纹，不参与当前向量召回。

## 3. 混合召回与重排序

主页资料 RAG 和课程 RAG 使用同一流程：

1. 中文关键词召回 Top 30。
2. 当前向量配置可用时执行精确 cosine 向量召回 Top 30。
3. 使用 RRF 合并并去重为 Top 20 候选。
4. 当前重排序配置可用时执行 Rerank。
5. 返回最终 Top 5 引用。

当前重排序 Provider：

- 硅基流动 `/v1/rerank`，默认 `BAAI/bge-reranker-v2-m3`。
- 阿里云百炼 Workspace `/compatible-api/v1/reranks`，默认 `qwen3-rerank`。
- 自定义兼容重排序服务。

向量未配置或失败时退回关键词召回；重排序未配置、超时、限流或失败时退回 RRF 混合排序。系统不把内容自动转发给另一 Provider，也不把规则 fallback 宣称为语义向量或模型重排。

## 4. 向量重建

切换默认向量配置不会自动消耗额度。用户在设置页显式点击“重建向量索引”后，前端调用：

```text
POST /api/v1/settings/model/embedding/reindex-jobs
```

该任务复用 `AIJobRuntime`、Redis/RQ、进度、取消、刷新恢复和失败重试。任务只处理当前用户可访问的课程切片和资料切片，按批次更新向量与配置指纹；同一配置重复执行会覆盖对应切片的当前向量，不创建重复记录。

新资料和新课程仍会 best-effort 生成当前默认配置的向量。既有资料未重建时关键词召回始终可用，命中的缺失切片可在后续流程中渐进补齐。

## 5. 引用字段

引用在原有字段基础上可返回：

```json
{
  "retrieval_source": "keyword | vector | hybrid",
  "embedding_status": "external | local_fallback | provider_failed",
  "embedding_provider": "xfyun_embedding",
  "embedding_dimension": 2560,
  "rerank_score": 0.91,
  "rerank_status": "completed | not_configured | provider_failed"
}
```

`content` 或 `snippet` 始终是受长度限制的安全片段。Trace 只允许返回调用次数、候选数、实际维度、降级状态和安全错误类别，不记录查询全文、资料原文、向量、密钥或 Provider 原始响应。

## 6. X2-Flash 边界

回答默认预设为讯飞 Spark X2-Flash：

```text
base_url = https://spark-api-open.xf-yun.com/agent/v1/
model = spark-x
```

主页和课程普通问题发送 `thinking.auto`，复杂比较、推导、诊断、规划与多证据综合发送 `thinking.enabled`。Provider 只消费最终 `content`，忽略 `reasoning_content`。Phase 25 起允许星火原生 `web_search`，但只有能提取可验证 URL 才进入证据链；否则回退 EduNova 外部搜索。其他 Provider 不接收未经验证的私有 thinking 参数。

## 7. 验收边界

- 混合维度向量可以落库，但一次查询只使用当前配置指纹对应的同维向量。
- 连接测试保存实际向量维度，用户不手填维度。
- 无向量 Key 时课程问答和主页资料问答仍可使用关键词证据。
- 无重排序 Key 时混合召回仍可返回引用。
- 免费额度只在 UI 中提示“以服务商控制台为准”，不写死额度或承诺永久免费。
- 标准自动测试使用 Mock/Stub，不消耗真实 API Key。

## 8. 话题切换与概念归并

- 会话追问由 `SemanticDecisionService` 结合裁剪后的真实消息输出独立问题、历史引用消息 ID 与置信度，不再用指代词或词项重合决定是否拼接。失败时保守使用当前问题，避免旧上下文污染召回。
- `MaterialComparisonGraph` 在判断共同重点前先按知识点 ID、规范化标题和概念别名归并证据。A*、A 星、启发式搜索和 `f(n)=g(n)+h(n)` 归为同一概念；反向传播与误差反传归为同一概念，同时保留每份资料自己的引用。
- Embedding 或 Rerank 降级仍允许关键词检索，但引用和 trace 必须返回实际 `retrieval_source`、`embedding_status` 与 `rerank_status`，不得把关键词结果描述为语义命中。

## 9. 章节保真资料切片

- 新资料只读取 `MaterialIngestionGraph` 已确认的目录版本。PDF 切片保留起止页，DOCX 保留标题样式，PPTX 保留幻灯片编号，Markdown 保留原生标题路径。
- 切片目标为 300 至 900 字，硬上限 1200 字，只允许在同一章节内部组合，不跨章节制造重叠上下文。
- 每个 `material_chunk` 保存章节路径、起止页、内容哈希、解析器版本和质量摘要。资料重新解析或目录编辑后通过目录版本区分结构。
- 主页资料问答、资料对比和智能建课共用已确认切片；待确认、失败和 legacy 资料不进入生产检索。
- 课程建成后，`knowledge_chunks` 继续绑定来源 `material_chunk`。关键词、向量、RRF 与可选 Rerank 的召回策略不变，但引用页码和章节来自已确认结构。

## 10. Phase 22 解析与检索边界

Docling 只替换 PDF、DOCX、PPTX 的通用结构提取，仍输出 EduNova 的 `ParsedDocument / ParsedPage / ParsedBlock`。目录确认、章节内切片、质量门禁、配置指纹、课程与用户隔离、混合召回、重排序和证据引用均不交给第三方框架。Phase 25 仅引入 LangChain 消息裁剪、`@tool` 和 `ToolNode`，不使用其 Loader、Memory、Agent 或 VectorStore 重写本链路。

## 11. Phase 23 外部补充边界

- 自动联网由 `SemanticDecisionService` 的结构化模型决策触发；它不是自由 Agent 工具调用，仍受用户、课程、权限、来源和显式强制规则约束。
- 课程切片继续使用原有 `chunk_id/material_id/knowledge_point_id` 证据合同；网页引用使用 `source_type=web` 与 `evidence_role=external_supplement`。
- 外部补充可以参与当次回答，但不得写入课程画像、弱点候选、掌握度、客观评分或教材证据绑定。

## 12. Phase 24 语义路由与画像边界

- 每条主页或课程消息最多增加一次路由模型调用，输出意图、搜索需求、搜索词、`auto/deep`、置信度、原因码和安全摘要。
- 模型输出使用 Pydantic 严格校验；非法 JSON、超时或无有效配置时，只有明确联网命令仍执行搜索，其他问题保持 `auto` 且不自动搜索。
- 课程资料检索仍在语义决策之后执行，实际课程命中由确定性证据策略决定是否允许网页补充。
- 同一次课程语义决策可以给出 `explicit_weakness/preference/goal/foundation` 候选，但必须高置信、具备课程引用并通过画像白名单和重复证据门禁；网页不成为画像证据。
- 未配置搜索、超时、限流、空结果均返回 warning 并保留课程或通用回答降级，不生成假 URL 或假来源。

## 13. Phase 25 原生搜索、历史与语义证据

- Provider 能力注册表只对白名单星火/官方 OpenAI 开启原生搜索；其他 OpenAI-compatible 地址默认 `none`。原生与外部搜索不会默认并行，只有前者失败或无可验证来源才回退。
- 外部搜索由 LangChain `@tool` 与 LangGraph `ToolNode` 执行，但节点选择、权限、超时、引用归一和降级仍由 EduNova Graph 控制。
- 历史对话引用使用 `source_type=history/evidence_role=conversation_memory`，排除当前会话且最多 5 条；它可以帮助理解上下文，但不得进入 RAG 教材证据、画像可信证据或课程闭环统计。
- 课程检索后执行结构化证据判断，输出 `direct/adjacent/off_topic`、相关 citation ID、证据充分性和外部搜索价值。返回的 citation ID 必须存在于真实候选，离题问题不得借联网绕过课程边界。
- 资料语义分类只补充资料类型、章节角色、知识领域、概念组、难度与置信度；低置信结果进入 `needs_review`。Docling 结构、目录、页码、切片、质量门禁和证据绑定保持确定性。

## 14. Phase 26 闭环行动与证据边界

下一最佳行动不是检索或生成节点，不向模型发送 Prompt，也不改变 RAG 排序。它可以读取现有掌握度、弱点和路径状态来决定“下一步去哪里”，但不能把网页、历史对话或未评分简答题提升为课程证据。课程切片、引用真实性、画像证据和评分边界保持 Phase 25 合同不变。
# Phase 27 外部视频与证据隔离

- 视频搜索词只包含知识点和必要的基础/目标短语，不发送课程原文、完整画像或历史私聊。
- `external_video` 引用使用 `source_type=web`、`evidence_role=external_supplement` 与 `generation_mode=curated_external`。
- 搜索摘要只证明“搜索服务返回了候选”，不能表示系统完整观看或验证了视频内容。
- 外部视频、观看进度和反馈不得进入课程切片、客观评分、掌握度、弱点或长期画像可信证据；反馈只调整当前课程的资源模态策略。

Phase 28 明确：资源反馈聚合不参与向量召回、RRF、Rerank、引用选择或课程相关性判断。它只作用于 RAG 之后的资源教学策略和路径学习包排序，因此 `helpful/not_helpful/too_hard/too_easy` 不能提高网页或视频成为课程证据的权重。

## Phase 29 国内来源优先边界

- `source_scope=mainland_preferred` 时，直接相关的大陆官方/高校来源优先，国际原始规范仍保留；国内社区只代表访问便利，不能压过直接相关的权威原始来源。
- `source_scope=global_required` 由语义模型在用户明确要求国外平台、原始论文/标准或问题必须依赖国际原始来源时选择，规则失败回退为 `mainland_preferred`。
- 引用增加 `access_scope=mainland_preferred|mainland_community|global_source|external_fallback`，不写“已验证可访问”。
- 视频查询先限制 `site:bilibili.com/video`；只有无合格 BV 结果时才执行 YouTube 查询。外部视频仍不进入课程 RAG、评分、掌握度或画像证据。

## Phase 31 大型教材证据验收

整本教材解析后必须校验源页范围、可读页比例、切片页码覆盖和目录异常，不能用前几页结果冒充完整 RAG 语料。真实验收抽查课程前、中、后部知识点，并要求问答引用与回答事实匹配。回答模型输出的数值、层级关系或领域结论若无法由当前课程证据支持，允许一次受控修复；仍不一致时回退为明确的证据型说明，不能保留貌似完整的幻觉答案。

可信画像中的个人难点可影响检索后的讲解方式和路径候选，但不改变召回事实、引用页码或课程证据权限。网页仍是“外部补充”，历史对话仍是“历史对话”，两者不能进入教材掌握度、练习评分或课程弱点证据。
# 图片问题与 RAG

视觉模型先把图片转换为经过校验的独立检索问题和安全摘要，随后沿用主页资料检索或课程 RAG。课程切片仍是教材事实与页码引用的唯一课程来源；图片只标记为“本次提问图片”，不得写入知识切片、向量索引、课程引用、掌握度或跨会话记忆。低置信视觉结果把不确定项明确交给回答链，不以 OCR 结果冒充结构图、波形或公式关系理解。

## Phase 38 跨课程生成约束

生成链路只读取当前用户、当前课程的目录、知识点、切片、合法引用、可信画像和课程级资源反馈。课程证据不足、目录未确认或切片质量未通过时拒绝生成，不由模型补写教材事实。学科适配以当前课程 `subject`、标题和知识点摘要进入路径、资源及练习 Prompt：程序设计可选代码，数学优先推导与图像，人文优先时间线与观点对比，语言课程优先语义与表达；任何模态仍需真实存在、权限合法并通过引用门禁。

Embedding 和 Rerank 的配置指纹、渐进补齐、关键词回退与用户/课程隔离没有变化。Provider 结构化能力只影响生成角色，不改变检索索引和旧向量可读性。
