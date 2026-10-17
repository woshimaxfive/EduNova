# 本地向量检索与迁移

默认检索融合本地向量与关键词，无需外部向量或重排序 Key。Windows 用户运行 02 启动入口；下方 Python 命令供开发验证。权重单独下载、只读挂载，不进入 Git。

## 准备和验证

在项目根目录、已有 Python 3.12 虚拟环境中执行：

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements-local-embedding.txt
.venv/Scripts/python.exe scripts/prepare_local_embedding.py
.venv/Scripts/python.exe -m backend.evals.local_embedding_check --output output/local-embedding/builtin-check.json
```

准备时联网下载固定版本的 BGE 中文小模型 ONNX 权重与分词配置，无需 Key；权重约 95 MB，运行前校验 SHA-256。缓存位于 `storage/models/bge-small-zh-v1.5`，报告位于 `output`，均被 Git 忽略。`--model-dir` 可指定下载和验证目录。

FastEmbed/ONNX Runtime 使用本机 CPU，默认 2 线程、每批 8 条，无需 Torch/GPU，不隐式下载其他模型。准备时缺文件或校验失败会报错，不回退云端。每个 Python 进程独立缓存推理实例，整套服务内存不能按单进程估算。

## 验证范围

- 使用内置数据结构课程的 56 个知识点正文，以独立检查问题作为查询；不把检查问题放进待检索正文。
- 对照当前关键词评分、纯向量和现有 RRF 公式的混合结果，输出首条与前 5 条命中数。
- 报告含目标排名、前五候选、词法/余弦/RRF 分数和相对关键词的首条改善或退化；检查分词长度，区分截断、近邻混淆与融合排序问题，仅输出内置合成课程诊断。
- 此实验不访问用户数据库、不读取模型凭证、不执行向量重建；不是外部向量服务对照或完整学习闭环验收。
- 保留课程和资料检索中的已有有效向量：普通查询只补齐缺失向量，不因配置改变自动覆盖旧向量。不同 profile 不混用；未迁移的资料仍可走关键词检索。
- 显式重建在同批事务中将旧向量及模型标识存入 `chunk_embedding_archives`，再替换当前向量。切回原配置重建时，同内容/profile 直接恢复归档、不调用外部模型；不同 profile 不混检，归档随原片段删除，不残留已删用户资料。
- 每批最多提交 8 个片段；取消或失败只回滚未提交批次。模型信息缺失、维度错误、数值无效或调用期间内容变化时拒绝替换，不补造旧模型身份。
- 升级前备份并运行 Alembic；有历史向量时拒绝降级删表。归档空间随片段数、profile 数与维度增长，不自动清除旧版本。
- Docker 与本地运行时默认采用本地模型，依据是免 Key、本机处理及当前样例可用；独立大样本与外部模型对照尚未完成。

## 默认启动与旧数据迁移

安装与启动统一按[部署指南](DEPLOYMENT.md)操作。已校验权重重复启动不下载；模型准备失败会停止后续启动步骤。

E2E 检查合成 Markdown 分块、本地 512 维向量落库、重读检索、章节引用与跨用户拒绝，从已解析资料开始，不替代上传解析验证。

模型准备后，`scripts/migrate_local_retrieval_env.ps1` 清理旧外部向量/重排序字段，启用本地 provider、保留主模型，不删除数据库历史列或向量归档。02 随后单独迁移语音配置，语音不借用向量凭证；本地模式不使用旧重排序凭证。

设置 `SYSTEM_EMBEDDING_PROVIDER=fastembed_local`，可选 `LOCAL_EMBEDDING_MODEL_DIR`（默认上文目录）和 `LOCAL_EMBEDDING_THREADS`（默认 2，范围 1–8）。该模式不读取主模型/外部向量凭证，固定模型 revision 纳入索引 profile。检索时缺文件回退关键词；损坏或推理失败则报错，不下载或转用付费服务。

默认后端与 AI worker 安装推理依赖、只读挂载同一权重，关闭外部重排序；各进程独立占用模型内存，缺目录则拒绝启动。旧索引在设置页通过重建任务迁移：先备份，失败后查任务详情，保留旧数据与评分。

单独验证本地推理（只使用合成内容，不访问数据库）：

```powershell
.venv/Scripts/python.exe -m backend.integration.local_embedding_check
```

完整集成检查运行 `./scripts/test_e2e.ps1`，使用并清理隔离测试数据库和数据卷，详见[脚本说明](../scripts/README.md)。

上述检查验证运行通路；新领域质量对照与高负载验收尚未完成，轻负载结果不代表性能上限。

## 来源与许可证

模型为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，MIT；固定 ONNX 导出来自 [Qdrant/bge-small-zh-v1.5](https://huggingface.co/Qdrant/bge-small-zh-v1.5/tree/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59)。推理使用 [FastEmbed](https://github.com/qdrant/fastembed)（Apache-2.0）与 ONNX Runtime（MIT）。本次只复用推理适配，不引入 Qdrant 数据库或替换 LangGraph、pgvector、权限和引用体系。
