# 本地向量验证（实验入口）

本目录说明可选的本地检索部署与离线验证入口，**尚未切换线上检索默认模型**，也没有把模型权重打包到 Git 或默认 Docker 镜像。普通用户暂时不需要执行这些步骤。

## 准备和验证

在项目根目录、已有 Python 3.12 虚拟环境中执行：

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements-local-embedding.txt
.venv/Scripts/python.exe scripts/prepare_local_embedding.py
.venv/Scripts/python.exe -m backend.evals.local_embedding_check --output output/local-embedding/builtin-check.json
```

准备步骤需要联网，但不需要模型 Key。下载固定版本的公开 BGE 中文小模型 ONNX 权重及分词配置，权重约 95 MB；运行前验证权重 SHA-256。缓存位于 Git 忽略的 `storage/models/bge-small-zh-v1.5`，报告位于 `output`，不随源码提交。可用 `--model-dir` 指定下载及验证目录。

推理通过 FastEmbed/ONNX Runtime 在本机 CPU 执行，默认 2 个线程、每批 8 条；不安装 Torch，不启用 GPU，也不隐式下载其他模型。文件缺失或校验失败会明确报错，不转用云端 Key。每个 Python 进程缓存一个推理实例；多个服务进程会分别占内存，不能把单进程实测当成整套部署的内存需求。

## 验证范围

- 使用内置数据结构课程的 56 个知识点正文，以独立检查问题作为查询；不把检查问题放进待检索正文。
- 对照当前关键词评分、纯向量和现有 RRF 公式的混合结果，输出首条与前 5 条命中数。
- 报告保存每题目标排名、前五候选及词法/余弦/RRF分数，单列相对关键词的首条退化与改善；同时检查实际分词长度，区分截断、近邻混淆和融合排序问题。只对内置合成课程输出这些诊断，不输出用户资料。
- 2026-09-24 同一56题复测：关键词首条50/前五55；纯向量46/54；混合由47/56改善为50/56。修复的是RRF同分时仅凭ID排序，改为先用已有词法分、仍同分才用ID；没有调权重或增加重排模型。最长文档328 tokens，无512窗口截断。仍有2题相对关键词退化、2题改善，不能据此声称全面优于旧方案，也不替代独立课程/外部模型对照。
- Windows 历史单进程资源采样：56篇文档含加载约7.871秒、56条查询约0.962秒，峰值工作集约368 MiB；本轮新进程复测含加载约3.192秒、查询约0.341秒。缓存状态和机器负载未控制，不能比较两轮速度；该数据也不代表整套部署内存或性能 SLA。
- 此实验不访问用户数据库、不读取模型凭证、不执行向量重建；不是外部向量服务对照或完整学习闭环验收。
- 保留课程和资料检索中的已有有效向量：普通查询只补齐缺失向量，不因配置改变自动覆盖旧向量。不同 profile 不混用；未迁移的资料仍可走关键词检索。
- 显式重建会先将当前向量及其模型标识保存在 `chunk_embedding_archives`，再替换当前检索向量，两者在同一批事务提交。切回原配置后再次提交重建，内容和 profile 一致的片段直接恢复归档向量，不调用外部模型；不同 profile 不混合检索。归档随原片段删除，不会保留已删除用户的资料。
- 重建仍按每批最多 8 个片段提交，取消或失败仅回滚尚未提交的批次，已完成批次保留。旧向量缺少模型信息、返回维度错误、数值无效、调用期间内容变化时拒绝替换；不会凭空补齐旧模型身份。
- 升级先备份数据库并执行 Alembic 迁移。历史向量存在时迁移拒绝降级删表。归档会额外占磁盘，近似随片段数、已使用 profile 数和维度增长；不会自动清除旧版本。
- 本地模型已接入可选运行时与Docker构建目标，尚未切换默认模型配置。当前已有单进程资源实测，但整套部署内存和独立/外部质量对照仍未完成，不建议直接切换生产默认值。

## 可选接入实际服务

Windows 用户可双击 `05_Start_Local_Retrieval.bat`，复用原启动流程并自动构建本地运行时、准备固定权重、断网试跑后启动。无需宿主机 Python。已校验权重重复启动不下载；准备失败不会切换现有容器。停止仍使用 `03_Stop_EduNova.bat`。后续启动本地模式请继续用05入口；02入口保留原外部配置，二者不是自动记忆的开关。

2026-09-24 隔离全栈轻负载实测：8个容器空闲内存合计约387 MiB；backend与AI worker各额外启动一个本地推理检查进程，完成3个合成查询并保留模型时，合计约854 MiB（`docker stats --no-stream`）。这不是请求进程原位加载的对比，也不是峰值；不包含Docker/WSL虚拟机、浏览器开销或PDF解析、高并发工作负载，不能据此建议1GB服务器。原有Docker内存建议不变。

新增真实PostgreSQL检查覆盖：合成Markdown正文分块、本地512维向量落库、重新读取后检索及章节引用、跨用户拒绝；使用真实推理与pgvector，仅替换调用审计/Redis协调层。它从已解析资料开始，不替代文件上传解析验收。`-LocalEmbedding` E2E已包含此检查。

本地覆盖明确禁止语音借用向量凭证。需要讯飞语音时请独立配置 `SYSTEM_SPEECH_APP_ID/API_KEY/API_SECRET`。确认05入口正常后，可清空 `.env` 中的 `SYSTEM_EMBEDDING_*` 与 `SYSTEM_RERANK_*` 外部配置，保留主模型和需要的独立语音配置；不要删除旧向量数据。清空后02入口不能恢复原外部检索，除非重新配置外部服务。本地模式会覆盖embedding provider，不要求 `.env` 保留向量Key。

本地运行时设置 `SYSTEM_EMBEDDING_PROVIDER=fastembed_local`，可选 `LOCAL_EMBEDDING_MODEL_DIR`（默认上文目录）及 `LOCAL_EMBEDDING_THREADS`（默认2，范围1–8）。不需要向量Key；此模式不读取主模型/外部向量凭证，固定模型revision参与索引profile。文件缺失时检索退回关键词；损坏或推理失败时报告失败，不下载或转用付费服务。

完成上文模型准备后，可选择Docker覆盖配置：

```powershell
docker compose -f docker-compose.yml -f docker-compose.local-embedding.yml up --build -d
```

覆盖配置仅为后端和AI worker安装可选推理依赖，并只读挂载同一份权重；同时关闭外部重排序，使用已有关键词与向量融合，不暗中调用旧重排Key。每个进程仍有独立模型内存；权重不进入镜像和Git。缺少宿主机模型目录时拒绝启动，不自动创建空目录。旧部署只有显式使用该覆盖文件才切换，不自动重建旧索引。移除覆盖配置、重新创建服务即可恢复原Provider；需要旧向量时按前文显式重建恢复。

运行时集成检查（只使用合成内容，不访问数据库）：

```powershell
.venv/Scripts/python.exe -m backend.integration.local_embedding_check
./scripts/test_e2e.ps1 -LocalEmbedding
```

这是运行通路验证，不是泛化质量验收。默认部署、新领域检索评测和整套资源验收仍需完成；当前阶段的明确结论是本地模式可选可用，但质量门禁尚未允许替换默认检索。

## 来源与许可证

模型为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，MIT；固定 ONNX 导出来自 [Qdrant/bge-small-zh-v1.5](https://huggingface.co/Qdrant/bge-small-zh-v1.5/tree/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59)。推理使用 [FastEmbed](https://github.com/qdrant/fastembed)（Apache-2.0）与 ONNX Runtime（MIT）。本次只复用推理适配，不引入 Qdrant 数据库或替换 LangGraph、pgvector、权限和引用体系。
