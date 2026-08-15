# EduNova

> 面向高校学生的可信、可解释个性化学习系统

EduNova 是面向高校学生的个性化学习系统。它把课程资料、学习画像、智能体协作、资源生成、练习诊断和学习报告连接为可持续优化的学习闭环。

```text
资料解析与建课 → 对话式学习画像 → 课程 RAG 辅导 → 个性化资源与路径
→ 练习诊断与薄弱点 → 再测与下一行动 → 学习报告与课程归档
```

## 核心能力

- **对话式动态画像**：通过自然语言与学习行为形成 8 个维度的学习画像，并区分全局偏好与课程级目标、基础和薄弱点。
- **十条 LangGraph 生产工作流**：覆盖资料解析、画像、智能建课、主页辅导、课程辅导、资源生成、路径规划、练习评估、报告生成和资料对比。
- **多资料建课与课程 RAG**：上传并确认多份资料后建课；课程问答优先使用课程证据，并展示可核对的来源。
- **多模态个性化资源**：支持讲解文档、思维导图、练习、代码、演示文稿、动画等资源；可保存版本并调整学习策略。
- **动态学习闭环**：根据路径、资源互动、练习、掌握度和弱点生成下一行动；再测结果会影响后续学习安排。
- **智能辅导与隐私控制**：支持流式问答、语音输入与朗读、图片问答、跨会话记忆开关和衍生记忆清除。
- **可靠性机制**：长耗时生成任务提供进度、恢复、取消和重试；模型或外部服务异常时采用明确的失败提示或安全降级，不伪造结果。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、TanStack Query、Radix UI、ECharts、Mermaid |
| 后端 | FastAPI、SQLAlchemy、Pydantic、Alembic、SSE |
| AI 编排 | LangGraph、LangChain 适配层、OpenAI-compatible 与讯飞等 Provider 适配 |
| 数据与任务 | PostgreSQL + pgvector、Redis、RQ |
| 文档与安全 | Docling、Pyodide 隔离代码验证、MIME 检测、可选 ClamAV |
| 部署 | Docker Compose、Nginx |

## 运行环境

- Docker Desktop 及 Docker Compose（建议分配不少于 8 GB 内存）
- 可访问 Docker 镜像与 Python/Node 依赖源的网络环境
- 如需体验 AI 生成、RAG 向量检索、图片或语音能力，需准备相应 Provider 的**个人或组织测试凭证**

> 本项目不包含、也不要求提交任何真实 API Key、账号密码、私有资料或个人学习数据。

## 快速启动

### Windows 一键启动（推荐）

在解压后的项目根目录中，按以下顺序双击：

```text
01_Check_Environment.bat
02_Start_EduNova.bat
```

首次启动会自动由 `.env.example` 创建仅供本机使用的 `.env`，并生成随机的 JWT 与配置加密密钥；不会生成或附带任何 AI Provider 凭证。启动后浏览器会自动打开 `http://127.0.0.1:8080`。

另外提供两个辅助脚本：

```text
03_Stop_EduNova.bat       停止服务并保留本机学习数据
04_Reset_Demo_Data.bat    删除本机演示数据，不可恢复
```

### 手动启动

### 1. 配置环境变量

复制示例文件：

```powershell
Copy-Item .env.example .env
```

首次使用至少修改 `.env` 中的以下安全项：

```text
POSTGRES_PASSWORD=
JWT_SECRET=
MODEL_SETTINGS_ENCRYPTION_KEY=
```

如需启用 AI 功能，再按所选 Provider 填写对应的模型、Embedding、Rerank、视觉或语音配置。未配置的能力会保持不可用或按页面提示安全降级，不会使用隐藏凭证。

### 2. 启动服务

```powershell
docker compose up -d --build
docker compose ps
```

首次构建需要下载依赖和文档解析模型，耗时取决于网络与机器配置。服务健康后访问：

```text
http://127.0.0.1:8080
```

注册时可选择“空白开始”或内置的“数据结构与算法”课程；也可上传自己的 Markdown、TXT、PDF、DOCX 或 PPTX 资料后创建课程。

### 3. 停止服务

```powershell
docker compose down
```

### 4. 清空本地演示数据（可选，且不可恢复）

```powershell
docker compose down -v
```

该命令会删除本机数据库、上传资料、聊天附件、导出文件与缓存，但不会删除源码和 Docker 镜像。

## 推荐演示路径

1. 注册并选择初始课程，或上传两份课程资料。
2. 确认资料目录，使用多份资料创建专题课程并查看资料对比。
3. 通过自然语言完善课程画像。
4. 在课程空间提问，查看流式回答、来源证据与协作轨迹。
5. 生成学习路径和多种资源，完成一次练习。
6. 查看薄弱点、再测、下一行动变化和学习报告。
7. 在设置页查看跨会话记忆与隐私控制；满足阶段条件后可归档并恢复课程。

## 项目结构

```text
backend/          FastAPI 服务、LangGraph 工作流、数据库迁移与后端测试
frontend/         React 前端、组件、路由与前端测试
code-verifier/    Pyodide 隔离代码验证服务
docker/           Dockerfile 与 Nginx 配置
evals/            离线 AI 质量评测
scripts/          开发、检查与测试脚本
docker-compose.yml Docker Compose 启动编排
.env.example      不含真实密钥的配置示例
VERSION.txt       最终提交源码基线标识
THIRD_PARTY_NOTICES.md 主要第三方组件与许可证说明
```

## 验证命令

```powershell
# 前端
Set-Location frontend
pnpm lint
pnpm test
pnpm build

# 回到仓库根目录后执行 Docker 配置检查
Set-Location ..
docker compose config
```

## 发布源码包说明

发布源码包应包含运行所需源码、Docker 配置、依赖清单、`.env.example`、本 README 与许可证；不应包含：

```text
.git/、.env、node_modules/、.venv/、dist/、storage/、var/、output/
缓存、日志、真实上传资料、导出文件、截图、测试账号数据、API Key
```

建议从已通过发布门禁的 `main` 提交导出源码包，确保发布内容与 GitHub 版本一致。

## 开源与开发辅助说明

主要第三方组件及许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [依赖许可证清单](docs/DEPENDENCY_LICENSES.md)。参与开发前请阅读 [贡献指南](CONTRIBUTING.md)；安全问题按 [安全策略](SECURITY.md) 私密报告。开发过程中使用 AI Coding 工具进行辅助开发；产品设计、范围决策、代码审查、测试与最终验收由维护者负责。

## 项目背景

EduNova 最初源于第十五届中国软件杯 A3 赛题，现作为独立的开源个性化学习项目维护。仓库不再分发赛题原文、答辩材料或竞赛内部交付文档。

## 许可证

本项目采用 [MIT License](LICENSE)。
