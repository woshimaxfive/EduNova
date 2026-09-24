# 启动与维护脚本

以下命令均从仓库根目录执行。普通使用者优先使用根目录 BAT；不必逐个运行这里的维护脚本。

## Windows 入口

| 文件 | 用途与影响 |
| --- | --- |
| `01_Check_Environment.bat` | 检查 Docker、Compose 与编排配置；不启动服务、不修改数据。 |
| `02_Start_EduNova.bat` | 初始化本机配置、准备本地模型、迁移旧配置、构建并启动服务。首次需要联网。 |
| `03_Stop_EduNova.bat` | 停止服务，保留数据卷。 |
| `04_Reset_Demo_Data.bat` | **删除项目数据卷中的全部学习数据**，不只删除演示账号；包括数据库、上传资料、附件、导出与缓存。不可恢复，先备份。 |

双击后窗口关闭太快时，可在 PowerShell 中执行 `cmd /c 01_Check_Environment.bat` 或 `cmd /c 02_Start_EduNova.bat` 查看结果。`02` 的健康检查和浏览器入口使用默认端口 `8080`；自定义端口请走[手动部署流程](../docs/DEPLOYMENT.md)。

`docker-compose.local-embedding.yml` 和 `docker-compose.search.yml` 仅保留旧命令兼容性，对应服务已经并入主编排，无需再叠加这些文件。

## 启动过程中的辅助脚本

| 脚本 | 作用 |
| --- | --- |
| `initialize_env.ps1` | 初始化本机安全配置，不提供 AI Key。 |
| `sync_postgres_password.ps1` | 将已有数据库角色密码与本机配置同步，属于数据库写操作。 |
| `prepare_local_runtime.ps1` | 用容器准备向量、语音模型并做离线检查；会构建镜像、下载并保存权重。 |
| `prepare_local_embedding.py`、`prepare_local_speech.py` | 固定模型的准备工具，通常由上一脚本调用。 |
| `migrate_local_retrieval_env.ps1` | 清除旧外部向量、重排序配置；不替用户重建历史索引。 |
| `migrate_local_search_env.ps1` | 清除旧外部搜索配置。 |
| `migrate_local_speech_env.ps1` | 清除旧外部语音配置。 |

迁移前自行备份 `.env` 和数据库；备份包含密钥，不要提交或打包。不要为了“整理”删除 `storage/models` 或备份目录。

## 开发验证与生成

| 脚本 | 使用场景 |
| --- | --- |
| `verify_encoding.ps1` | 检查受管理文本及未忽略新文件的 UTF-8 无 BOM 编码，包含 BAT/CMD。 |
| `test.ps1` | 综合回归入口：后端、前端、类型/构建、合同和配置等检查。 |
| `test_e2e.ps1` | 启动并清理隔离的 `edunova-e2e` Docker 项目及其测试数据卷；会构建镜像，需要本地模型。 |
| `test_local_search_setup.ps1`、`test_local_speech_setup.ps1` | 使用临时合成配置测试旧配置迁移，不改真实 `.env`。 |
| `run_ai_eval.ps1` | AI 评测入口；执行前检查参数与评测范围。 |
| `check_openapi.py`、`export_openapi.py` | 检查或导出 OpenAPI 合同。 |
| `supply_chain.ps1`、`generate_dependency_licenses.py` | 供应链检查与许可证清单维护；可能需要联网。 |
| `check_live_models.py` | 检查真实模型服务，可能产生调用费用。 |
| `diagnose_live_performance.py`、`diagnose_rag_latency.py`、`diagnose_semantic_structure.py`、`measure_release_performance.py` | 定向诊断或性能取证；先检查参数，可能访问模型、数据库或现有环境，不作为普通启动步骤。 |

常用回归命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_encoding.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1
# 跨服务变更时另外运行；会重置隔离测试项目，勿在该项目中保存真实数据
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_e2e.ps1
```

更新接口合同后，在根目录使用项目 Python 环境运行 `python scripts/export_openapi.py`，再在 `frontend` 中运行 `pnpm exec openapi-typescript ../backend/openapi.json -o src/types/openapi.generated.ts`。两份生成文件一起检查与提交。

脚本退出成功不等于模型质量或性能已达标；评测报告中的 `evidence_gap`、失败项与未验证范围需要单独核对。开发流程见[贡献指南](../CONTRIBUTING.md)。
