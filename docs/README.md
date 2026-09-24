# 文档索引

首次使用请从根目录的 [README](../README.md) 开始。本页负责导航；具体行为以当前代码和对应专题文档为准。

## 使用与部署

| 想做什么 | 阅读入口 |
| --- | --- |
| 注册、建课、问答、练习与报告 | [用户指南](USER_GUIDE.md) |
| 安装、配置、升级与生产加固 | [部署指南](DEPLOYMENT.md) |
| 分清 BAT 和维护脚本，避免误删数据 | [脚本说明](../scripts/README.md) |
| 准备本地向量模型、迁移旧索引 | [本地检索](LOCAL_EMBEDDING.md) |
| 了解免 Key 搜索及网络限制 | [联网搜索](KEYLESS_SEARCH.md) |
| 语音识别、浏览器朗读及许可边界 | [本地语音](LOCAL_SPEECH.md) |
| 了解记忆、个人资料与数据清除 | [隐私说明](PRIVACY.md) |

## 开发与维护

| 内容 | 阅读入口 |
| --- | --- |
| 提交流程与验证要求 | [贡献指南](../CONTRIBUTING.md) |
| 服务分层与数据流 | [系统架构](ARCHITECTURE.md) |
| HTTP 接口合同 | [API 文档](API.md) |
| 实体与迁移 | [数据库设计](DATABASE_DESIGN.md) |
| 工作流、状态及质量约束 | [Agent 设计](AGENT_DESIGN.md) |
| 检索、证据与引用 | [RAG 设计](RAG_DESIGN.md) |
| 内置课程的内容质量边界 | [内置课程质量](BUILTIN_COURSE_QUALITY.md) |
| 技术安全机制 | [安全设计](SECURITY.md) |
| 私密报告漏洞 | [仓库安全政策](../SECURITY.md) |
| 第三方组件与依赖许可 | [第三方声明](../THIRD_PARTY_NOTICES.md)、[依赖清单](DEPENDENCY_LICENSES.md) |

## 代码从哪里看

- `backend/app/api`、`schemas`：接口与输入输出合同。
- `backend/app/services`、`models`、`db`：领域逻辑、实体与事务支持。
- `backend/app/agents`、`providers`、`workers`：工作流、外部能力适配与任务执行。
- `backend/migrations`、`tests`、`integration`：数据库历史、单元回归与集成验证。
- `frontend/src/app`、`pages`、`features`：应用入口、页面与功能组织。
- `frontend/src/components`、`styles`：组件与样式；`api`、`types`：接口调用与类型。
- `docker`、`code-verifier`、`evals`：部署配置、隔离代码验证与 AI 评测。

`backend/openapi.json` 与 `frontend/src/types/openapi.generated.ts` 是生成合同，不应当作垃圾删除或手工改写；更新入口见[脚本说明](../scripts/README.md)。数据库迁移同样需要保留历史，不能仅保留最新文件。

## 哪些不是公开文档

`docs/local/`、`.planning/` 和 `output/` 用于本地计划、过程记录或运行产物，不纳入公开源码。`.env`、`storage/`、`var/` 可能包含密钥、模型、备份或用户数据，不能仅因不受 Git 管理就删除。`docs/assets/` 的公开产品预览图属于文档资源。
