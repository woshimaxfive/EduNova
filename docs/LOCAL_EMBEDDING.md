# 本地向量检索与迁移

本地向量是默认检索方式，与关键词融合排序，不需要外部向量或重排序Key。Windows用户直接运行02启动入口即可；下列Python步骤供开发者验证使用。模型权重不进入Git，单独下载并只读挂载。

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
- 此实验不访问用户数据库、不读取模型凭证、不执行向量重建；不是外部向量服务对照或完整学习闭环验收。
- 保留课程和资料检索中的已有有效向量：普通查询只补齐缺失向量，不因配置改变自动覆盖旧向量。不同 profile 不混用；未迁移的资料仍可走关键词检索。
- 显式重建会先将当前向量及其模型标识保存在 `chunk_embedding_archives`，再替换当前检索向量，两者在同一批事务提交。切回原配置后再次提交重建，内容和 profile 一致的片段直接恢复归档向量，不调用外部模型；不同 profile 不混合检索。归档随原片段删除，不会保留已删除用户的资料。
- 重建仍按每批最多 8 个片段提交，取消或失败仅回滚尚未提交的批次，已完成批次保留。旧向量缺少模型信息、返回维度错误、数值无效、调用期间内容变化时拒绝替换；不会凭空补齐旧模型身份。
- 升级先备份数据库并执行 Alembic 迁移。历史向量存在时迁移拒绝降级删表。归档会额外占磁盘，近似随片段数、已使用 profile 数和维度增长；不会自动清除旧版本。
- 本地模型已成为默认运行时与Docker配置。选择依据是免Key、本机处理与当前样例可用，不代表全面优于外部模型；独立大样本和外部模型对照仍未完成。

## 默认启动与旧数据迁移

Windows用户双击 `02_Start_EduNova.bat`：构建本地运行时、准备固定权重、断网试跑后启动。无需宿主机Python。已校验权重重复启动不下载；准备失败不会切换现有容器。停止使用 `03_Stop_EduNova.bat`。非Windows部署先准备权重，再执行默认Compose。

新增真实PostgreSQL检查覆盖：合成Markdown正文分块、本地512维向量落库、重新读取后检索及章节引用、跨用户拒绝；使用真实推理与pgvector，仅替换调用审计/Redis协调层。它从已解析资料开始，不替代文件上传解析验收。`-LocalEmbedding` E2E已包含此检查。

启动脚本在模型准备成功后执行 `scripts/migrate_local_retrieval_env.ps1`：移除旧外部向量/重排序字段，设置本地provider并保留主模型。语音现已使用独立本地服务，不再复制或借用向量凭证；02随后单独清理旧语音配置。本地模式禁止旧重排序凭证生效；不删除数据库历史配置列或向量归档。

本地运行时设置 `SYSTEM_EMBEDDING_PROVIDER=fastembed_local`，可选 `LOCAL_EMBEDDING_MODEL_DIR`（默认上文目录）及 `LOCAL_EMBEDDING_THREADS`（默认2，范围1–8）。不需要向量Key；此模式不读取主模型/外部向量凭证，固定模型revision参与索引profile。文件缺失时检索退回关键词；损坏或推理失败时报告失败，不下载或转用付费服务。

完成模型准备后，默认Docker配置即可使用：

```powershell
docker compose up --build -d
```

默认配置为后端和AI worker安装推理依赖，并只读挂载同一份权重；关闭外部重排序。每个进程有独立模型内存；缺少模型目录时拒绝启动。原 `docker-compose.local-embedding.yml` 仅保留兼容入口。既有索引通过现有设置页重建任务迁移：先备份数据库，再提交重建；任务按批次归档旧向量后替换，失败需检查任务详情，不删除旧数据或评分记录。

运行时集成检查（只使用合成内容，不访问数据库）：

```powershell
.venv/Scripts/python.exe -m backend.integration.local_embedding_check
./scripts/test_e2e.ps1 -LocalEmbedding
```

这是运行通路验证，不是泛化质量验收。默认部署已采用本地方案；新领域质量对照与高负载资源验收仍未完成，不将轻负载快照宣传为性能上限。

## 来源与许可证

模型为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，MIT；固定 ONNX 导出来自 [Qdrant/bge-small-zh-v1.5](https://huggingface.co/Qdrant/bge-small-zh-v1.5/tree/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59)。推理使用 [FastEmbed](https://github.com/qdrant/fastembed)（Apache-2.0）与 ONNX Runtime（MIT）。本次只复用推理适配，不引入 Qdrant 数据库或替换 LangGraph、pgvector、权限和引用体系。
