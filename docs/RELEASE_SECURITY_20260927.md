# 发布候选安全检查记录（2026-09-27）

## 历史密钥匹配

Gitleaks 检查全部 431 个历史提交。新增三条精确指纹例外均来自同一隔离 E2E 合成登录密码，分别位于 `backend/integration/learning_closure_check.py`、`frontend/e2e/evidence-closure.spec.ts`、`frontend/e2e/resource-rendering.spec.ts`。

`learning_closure_check.seed()` 明确创建并散列合成测试密码；`scripts/test_e2e.ps1` 在 `edunova-e2e` Compose 项目内执行 seed 与 verify，浏览器用例登录该账号。它们不是外部 Provider Key，也不是默认应用账号。例外只匹配提交、路径、规则和行号，不忽略整个文件或提交。例外后历史扫描通过；待提交源码另行导出扫描。

## Python 依赖

原开发测试依赖 httpx2 2.11.0 命中 CVE-2026-84382，已固定到 2.12.0 并安装验证。保留现有 HTTP 接口和测试栈，不引入新适配框架。维护者的 [修复公告](https://github.com/pydantic/httpx2/releases/tag/v2.12.0) 说明压缩响应改为有界增量解压；[漏洞记录](https://github.com/advisories/GHSA-8xx6-hgc6-gc2m) 列出修复版本。

对运行、AI、语音、向量、桌面和开发依赖的固定声明执行 `pip-audit --disable-pip --no-deps` 后未发现已知漏洞。该检查不自动证明所有传递依赖或原生二进制安全；本机已安装包另行审计。当前 LocalTest 清单中没有 httpx2，因此本次开发依赖升级不改变该安装器字节。

可选 `requirements-eval-network.txt` 的 Ragas 0.4.3 命中 [CVE-2026-6587](https://github.com/advisories/GHSA-95ww-475f-pr4f)，审计未给出修复版本。入口 `backend/evals/ragas_trend.py` 仅在显式启用网络评测时导入 Ragas，没有调用该多模态指标；业务运行目录没有 Ragas 导入，现有 44,381 文件载荷中也不包含它。保持可选依赖隔离，不将完整可选评测依赖集合描述为零漏洞，不在不可信资料上启用它。本次没有盲目更换评测框架；后续采用上游修复版本须重新验证。

## 本机传递依赖与旧载荷

对本机全部已安装包另行审计发现 AnyIO 4.14.1、aiohttp 3.14.1、pip 26.1.2、pyasn1 0.6.3、soupsieve 2.8.4 以及无计划修复的 ecdsa 0.19.2。按实际包元数据核查后，AnyIO 属于当前 HTTP/ASGI 运行链，已在运行依赖中固定并安装 4.14.2，`pip check` 通过；[上游修复说明](https://github.com/agronholm/anyio/releases/tag/4.14.2) 覆盖 TLS 域名、子进程补充组与进程池 stderr 问题。

其余名称中，aiohttp 来自本机 langchain-community 等可选环境，ecdsa/pyasn1 来自遗留 python-jose（项目认证已使用 PyJWT），soupsieve 来自 Beautiful Soup。本轮未把这些不在当前安装载荷中的本机包强加为运行依赖，也未删除用户环境中的遗留工具；本机全环境审计因此不能报告全绿。

逐项查现有 LocalTest 清单：AnyIO 为 4.14.1，搜索 Python 包含 pip 25.0.1；其余上述名称不在载荷。旧 EXE 保留以复现此前验收，不将源码依赖更新冒充为 EXE 更新。分发前必须使用修复版 AnyIO，并更新或从只读运行环境移除不需要的 pip，重建载荷、通知与哈希后重新安装验证。旧载荷仍由 `redistributionReviewed=false` 阻断正式打包。

## JavaScript 依赖及桌面边界

前端 pnpm、桌面 npm、代码验证器 npm 审计均通过。桌面测试覆盖麦克风权限、导出发起者、IPC 来源、路径校验、资源清单和未审查分发阻断；真实 Pyodide 用例覆盖受限内置引用和别名绕过。此范围不包括完整 OS 沙箱逃逸证明，也不代替操作系统补丁或人工使用验收。

## 尚未闭合的证据

Sherpa v1.13.8 的 [eSpeak 构建配方](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/cmake/espeak-ng-for-piper.cmake) 固定源码归档和 SHA-256，本地已取得对应源码和许可证。但安装的预编译 wheel 与完整构建材料的对应核对仍未完成；仅有仓库顶层 Apache 许可证不足以代表全部捆绑组件。SenseVoice 转换仓库许可缺项见分发记录。当前不上传 EXE、不修改分发审查标记。
