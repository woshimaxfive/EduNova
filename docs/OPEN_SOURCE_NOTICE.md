# EduNova 开源说明

更新时间：2026-07-05

## 1. 许可证

EduNova 采用 MIT License。许可证全文见仓库根目录 `LICENSE`。

MIT License 允许使用、复制、修改、合并、发布、分发、再许可和销售本项目副本，但必须保留版权声明和许可证声明。本项目按“现状”提供，不提供适销性、特定用途适用性或非侵权担保。

## 2. 第三方依赖

EduNova 使用的主要开源技术包括：

| 层 | 依赖 |
| --- | --- |
| 前端 | React、Vite、TypeScript、Tailwind CSS、React Router、React Query、Zustand、ECharts、Mermaid、Markmap、CodeMirror、Pyodide 0.29.2、Radix UI、Phosphor Icons |
| 文档与课件 | python-docx、reportlab、python-pptx |
| 后端 | FastAPI、SQLAlchemy、Alembic、Pydantic、PyJWT、bcrypt、httpx、cryptography、LangGraph |
| 数据 | PostgreSQL、pgvector、Redis |
| 工程 | Docker Compose、Nginx、pytest、Vitest、ESLint、ruff |

开源发布前应以锁文件和镜像版本为准复核第三方许可证。当前文档记录项目层面的开源边界，不替代最终依赖许可证审计。

## 3. 参考项目边界

EduNova 的产品设计参考了 RAG、个性化学习、多智能体可观测性和开源学习平台的通用做法，但仓库代码不应直接复制第三方项目实现。

如后续引入外部代码片段、课程包、图标集、模板或数据集，必须同时记录：

- 来源链接。
- 许可证。
- 修改方式。
- 是否允许再分发。
- 是否包含用户数据或受版权保护内容。

## 4. 不可提交内容

以下内容不能进入 Git 仓库：

- 真实 `.env`。
- 真实 API Key、JWT、密码、数据库连接密码和模型密钥。
- 用户上传的私有资料。
- 用户真实学习记录、作答、画像原文和报告。
- 完整系统提示词、完整模型输入和完整资料原文。
- 本地缓存、日志、构建产物和下载文件。

当前仓库只允许提交安全示例值，例如：

```text
SYSTEM_MODEL_API_KEY=replace-with-your-own-key
JWT_SECRET=change-this-local-development-secret
```

这些值只能用于本地开发示例，不能用于生产部署。

## 5. 模型与密钥

EduNova 支持两类模型配置：

- 用户自己的 OpenAI-compatible 配置。
- 服务器 `.env` 中的统一兜底配置。

密钥处理规则：

- 用户 API Key 加密保存，接口只返回脱敏信息。
- 服务器 Key 只放在 `.env` 或部署平台密钥管理中。
- 日志、Agent trace、报告、导出和错误响应不能输出明文 Key。
- 模型不可用时必须显示未配置、低依据或本地 fallback，不能伪装成真实模型输出。

## 6. 数据和隐私

EduNova 第一版是多用户系统，所有课程、资料、画像、资源、路径、练习、报告和导出都必须按当前用户隔离。

开源试用时建议：

- 使用临时账号。
- 使用示例课程或公开可分享资料。
- 不上传真实考试资料、隐私文件或未授权教材。
- 清理 Docker volume 后再共享演示环境。

## 7. 开源前检查

发布前至少运行：

```powershell
.\scripts\verify_encoding.ps1
.\scripts\test.ps1
docker compose config --quiet
git diff --check
git status --short --branch
```

并检查：

- `.env` 未被跟踪。
- `var/uploads`、`storage`、`output`、`node_modules`、`dist` 未被提交。
- 文档不包含真实账号、密钥或私有资料。
- 浏览器验收记录使用临时账号和示例课程。
