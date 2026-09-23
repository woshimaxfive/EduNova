# 本地向量验证（实验入口）

本目录说明的是可重复的离线验证入口，**尚未切换线上检索默认模型**，也没有把模型权重打包到 Git 或默认 Docker 镜像。普通用户暂时不需要执行这些步骤。

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
- 此实验不访问用户数据库、不读取模型凭证、不执行向量重建；不是外部向量服务对照或完整学习闭环验收。
- 保留课程和资料检索中的已有有效向量：普通查询只补齐缺失向量，不因配置改变自动覆盖旧向量。不同 profile 不混用；未迁移的资料仍可走关键词检索。
- 原有显式重建任务仍是改写操作，**不要用它试验新模型**。版本化并存、回滚入口、Docker 默认打包以及外部质量对照尚待完成，未完成前不建议切换生产默认值。

## 来源

模型为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，MIT；固定 ONNX 导出来自 [Qdrant/bge-small-zh-v1.5](https://huggingface.co/Qdrant/bge-small-zh-v1.5/tree/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59)。推理使用 [FastEmbed](https://github.com/qdrant/fastembed)（Apache-2.0）与 ONNX Runtime（MIT）。本次只复用推理适配，不引入 Qdrant 数据库或替换 LangGraph、pgvector、权限和引用体系。
