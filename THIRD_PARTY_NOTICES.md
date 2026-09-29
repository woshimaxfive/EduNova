# 第三方软件与许可证说明

EduNova 项目源码采用根目录 [MIT License](LICENSE) 发布。本文件说明项目运行涉及的主要第三方组件；实际版本与完整依赖树以 `backend/requirements*.txt`、`frontend/package.json`、`frontend/pnpm-lock.yaml`、`code-verifier/package.json`、`code-verifier/package-lock.json`、`desktop/package.json`、`desktop/package-lock.json` 和 Docker Compose 配置为准。这些声明及锁文件不替代最终交付包的完整组件清单和许可证正文。

本项目不复制或分发用户上传资料、模型返回内容、第三方教材、API Key 或 Provider 账号凭证。

| 组件 | 用途 | 声明许可证 | 来源 |
| --- | --- | --- | --- |
| React、TypeScript、Vite | Web 前端 | MIT | https://react.dev / https://www.typescriptlang.org / https://vite.dev |
| TanStack Query、Zustand、Radix UI | 前端状态与无障碍组件 | MIT | https://tanstack.com/query / https://zustand.docs.pmnd.rs / https://www.radix-ui.com |
| ECharts、Mermaid | 图表与图形表达 | Apache-2.0、MIT | https://echarts.apache.org / https://mermaid.js.org |
| FastAPI、Pydantic、SQLAlchemy、Alembic | API、数据校验、ORM 与迁移 | MIT | https://fastapi.tiangolo.com / https://docs.pydantic.dev / https://www.sqlalchemy.org / https://alembic.sqlalchemy.org |
| LangChain、LangGraph | 模型与状态化工作流适配 | MIT | https://github.com/langchain-ai/langchain / https://github.com/langchain-ai/langgraph |
| PostgreSQL、pgvector | 关系数据与向量检索 | PostgreSQL License | https://www.postgresql.org / https://github.com/pgvector/pgvector |
| Redis 8.0 | 队列与进度存储 | RSALv2、SSPLv1 或 AGPLv3（三选一） | https://redis.io/legal/licenses/ |
| RQ | 后台任务 | BSD-2-Clause | https://python-rq.org |
| Docling | 文档结构提取 | MIT | https://github.com/docling-project/docling |
| Electron（开发态桌面宿主） | 桌面窗口 | MIT；Chromium/Node及捆绑组件另有通知 | https://github.com/electron/electron |
| pywin32 | Windows进程生命周期 | PSF；以实际包内许可证为准 | https://github.com/mhammond/pywin32 |
| Docling Heron / TableFormer模型 | PDF版面与表格推理 | 与Docling代码分开；实际固定模型卡分别声明Apache-2.0 / CDLA-Permissive-2.0 | https://huggingface.co/docling-project/docling-layout-heron / https://huggingface.co/docling-project/docling-models |
| FastEmbed、ONNX Runtime（可选） | 本地 CPU 向量验证 | Apache-2.0、MIT | https://github.com/qdrant/fastembed / https://github.com/microsoft/onnxruntime |
| BAAI/bge-small-zh-v1.5（可选下载） | 中文 512 维向量模型 | MIT | https://huggingface.co/BAAI/bge-small-zh-v1.5 |
| Pyodide | 隔离式 Python 代码验证运行时 | MPL-2.0 | https://pyodide.org |
| Nginx | 统一 Web 入口与反向代理 | BSD-2-Clause | https://nginx.org |
| SearXNG（默认搜索容器） | 免Key联网搜索聚合 | AGPL-3.0-or-later | https://github.com/searxng/searxng |
| Trafilatura、HTTPCore | 本地网页正文提取、受限公开网页读取 | Apache-2.0、BSD-3-Clause | https://github.com/adbar/trafilatura / https://github.com/encode/httpcore |

## 运行时服务说明

主模型通过可配置Adapter接入外部服务，图片理解跟随主模型；账号和凭证不随源码分发。默认向量、排序及语音在本地运行，SearXNG搜索仍访问外部网站。历史检索Provider适配保留兼容，默认配置不使用其凭证。

本地语音采用Sherpa-ONNX 1.13.8（仓库Apache-2.0；当前预编译包包含espeak-ng/piper等GPL组件）、SenseVoice（FunASR MODEL_LICENSE 1.1）；朗读改用浏览器本地中文声音，不再下载或加载Kokoro。不得将整套运行时标注为纯MIT/Apache。固定来源、模型许可、分发义务和试验边界见[本地语音说明](docs/LOCAL_SPEECH.md)；本仓库不分发预构建语音镜像。

语音资产分为本地默认与桌面分发两种配置：本地准备脚本默认使用 2025 粤语转换权重，桌面分发使用 `--release-model` 对应的 2024 转换权重。两者来源与摘要分别记录在 `desktop/model-assets.lock.json` 和 `desktop/release-model-assets.lock.json`，不能混用许可结论。具体来源和使用方式见[本地语音说明](docs/LOCAL_SPEECH.md)，随包材料要求见[桌面分发说明](docs/DESKTOP_DISTRIBUTION.md)。

## 合规边界

1. 使用者可通过本源码包中的依赖清单与 Docker Compose 复现本地运行环境。
2. 各第三方组件仍受其自身许可证约束；本项目的 MIT License 不改变第三方许可证。
