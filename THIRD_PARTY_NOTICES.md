# 第三方软件与许可证说明

EduNova 项目源码采用根目录 [MIT License](LICENSE) 发布。本文件说明项目运行涉及的主要第三方组件；实际版本与完整依赖树以 `backend/requirements*.txt`、`frontend/package.json`、`frontend/pnpm-lock.yaml`、`code-verifier/package.json`、`code-verifier/package-lock.json` 和 Docker Compose 配置为准。

本项目不复制或分发用户上传资料、模型返回内容、第三方教材、API Key 或 Provider 账号凭证。

| 组件 | 用途 | 声明许可证 | 来源 |
| --- | --- | --- | --- |
| React、TypeScript、Vite | Web 前端 | MIT | https://react.dev / https://www.typescriptlang.org / https://vite.dev |
| TanStack Query、Zustand、Radix UI | 前端状态与无障碍组件 | MIT | https://tanstack.com/query / https://zustand.docs.pmnd.rs / https://www.radix-ui.com |
| ECharts、Mermaid | 图表与图形表达 | Apache-2.0、MIT | https://echarts.apache.org / https://mermaid.js.org |
| FastAPI、Pydantic、SQLAlchemy、Alembic | API、数据校验、ORM 与迁移 | MIT | https://fastapi.tiangolo.com / https://docs.pydantic.dev / https://www.sqlalchemy.org / https://alembic.sqlalchemy.org |
| LangChain、LangGraph | 模型与状态化工作流适配 | MIT | https://github.com/langchain-ai/langchain / https://github.com/langchain-ai/langgraph |
| PostgreSQL、pgvector | 关系数据与向量检索 | PostgreSQL License | https://www.postgresql.org / https://github.com/pgvector/pgvector |
| Redis 7.2、RQ | 队列、进度与后台任务 | BSD-3-Clause、BSD-2-Clause | https://redis.io / https://python-rq.org |
| Docling | 文档结构提取 | MIT | https://github.com/docling-project/docling |
| Pyodide | 隔离式 Python 代码验证运行时 | MPL-2.0 | https://pyodide.org |
| Nginx | 统一 Web 入口与反向代理 | BSD-2-Clause | https://nginx.org |

## 运行时服务说明

本项目通过可配置 Adapter 接入 OpenAI-compatible、讯飞及其他由部署方明确配置的模型、向量、重排序、视觉、语音和搜索服务。此类服务的账号、密钥、价格、可用性与服务条款由部署方和对应 Provider 管理，不随本项目源码分发。

## 合规边界

1. 使用者可通过本源码包中的依赖清单与 Docker Compose 复现本地运行环境。
2. 各第三方组件仍受其自身许可证约束；本项目的 MIT License 不改变第三方许可证。
