# Electron Windows 桌面客户端

最新 DOCX 修复验收包位于 `dist/local-test-docxfix`，已完成实际安装、空数据启动、重启、卸载保留数据和真实模型练习/对话/PDF/DOCX 导出续验。Word 显式标题修复通过 31 项相关回归。旧 `dist/local-test` 作为基线保留；两者均为未签名 LocalTest，尚未完成干净 Windows、人工硬件及第三方完整分发审查。

这是直接复用现有 EduNova 前端的 Windows 桌面宿主源码。NSIS 本机试装包已通过实际安装、空数据启动、重启持久化和卸载保留数据验收，产物位于 `dist/local-test`。该包未签名，干净 Windows 验收与第三方完整分发核对仍未完成；详细证据和边界见 `../docs/DESKTOP_DISTRIBUTION.md` 顶部记录。Electron 官方运行时位于被忽略的 node_modules，属于开发依赖。

## 安装器构建

固定使用 electron-builder 26.15.3，提供 `npm.cmd run pack:check --prefix desktop`、`pack:dir` 和 `dist`。设置 `EDUNOVA_PAYLOAD_DIR` 为独立安装资源目录的绝对路径。资源清单必须完整、逐文件哈希匹配，并已完成分发材料核对；检查失败时不生成安装器，不自动发布。

`scripts/assemble_desktop_payload.py` 从已验证运行时和当前应用源码白名单组装新候选目录，拒绝覆盖旧目录，默认保留 `redistributionReviewed=false`。它复用本机验证资产，尚不是从全新开发环境下载并重建全部依赖的发布流水线。

分发核对未完成时可显式运行 `node desktop/packaging.cjs --local-test` 生成本机试装包，输出独立位于 `desktop/dist/local-test`，不得视作正式分发通过。构建固定采用现有构建器支持的 `BCJ` 过滤器，避免旧 NSIS 解压器跳过自动 ARM64 过滤的辅助二进制。过深的 Python 许可证路径会保留原始字节并迁至 `notices/python`，原路径、安装路径和哈希记在 `notices/relocated-license-paths.json`，不能直接删除许可证来规避长路径问题。

安装器为当前用户安装，不请求提权，创建快捷方式，卸载时保留用户数据，不自动启动应用。安装版首次运行调用随包 `desktop_prepare.py`，在 `%APPDATA%/EduNova` 创建持久凭据、数据库、模型配置加密密钥、上传文件和窗口 profile；安装资源目录仅提供运行程序和模型。开发态仍使用下面的显式配置。

Windows 启动器可能重定向 AppData；准备程序按物理目录核对 profile，允许同一目录的逻辑/重定向路径，同时拒绝不同的用户数据目录。

首次启动程序已接入数据库初始化/迁移、Redis、离线语音、API、Windows RQ worker、搜索和独立代码执行；本机候选验证与实际安装包验收分别记录，不能仅凭候选清单生成成功就称为完整交付。

## 运行

```powershell
npm.cmd ci --prefix desktop
node desktop/node_modules/electron/install.js
$env:EDUNOVA_DESKTOP_CONFIG = 'C:/EduNova/desktop.json'
npm.cmd start --prefix desktop
```

Electron 44.4.5 的官方 npm 包将二进制安装作为显式命令，第二步使用随包 checksums 校验官方运行时。Node 需符合该版本包声明（>=22.12.0）。不把开发运行时当作最终交付包。

配置由可信主进程读取，不放进 renderer。路径均为绝对路径：

```json
{
  "python": "C:/EduNova/runtime/python/python.exe",
  "bridge": "C:/EduNova/app/scripts/desktop_host_bridge.py",
  "manifest": "C:/EduNova/data/runtime.json",
  "userData": "C:/EduNova/data/window-profile",
  "url": "http://127.0.0.1:18080/login"
}
```

URL 必须是 manifest 中有健康探针的同一个回环服务 origin。该配置需要已准备的原生服务与模型，示例并非完整分发配置。不要提交实际凭据、用户profile或本机manifest。Python控制器合同见 `../docs/DESKTOP_RUNTIME.md`。

## 行为与边界

- 窗口显示启动页，主进程请求Python宿主桥启动服务，收到成功消息后加载已有前端。
- 主窗口关闭会先断开宿主桥，让其关闭自身后台服务，再退出Electron。主进程异常退出后管道EOF触发同一清理链。
- 同一userData的第二个实例聚焦已有窗口。各次隔离试验使用独立profile，避免触碰真实用户登录资料。
- renderer启用sandbox/contextIsolation/webSecurity，关闭Node及webview，仅暴露固定status/quit；主进程核对拥有的webContents、顶层frame和精确origin，并拒绝额外IPC参数。
- 拒绝弹窗、跨origin导航/重定向、远端网络请求和未明确允许的权限，不把renderer变成可发送命令的终端。
- 麦克风仅允许本窗口的同源顶层页面申请纯音频输入，先显示确认框，默认拒绝。确认只在当前文档有效；刷新或重新打开后再次询问。摄像头、屏幕录制、子页面和其他来源继续拒绝；等待确认期间发生导航会使请求失效。系统麦克风权限仍由Windows控制。
- 复用现有Blob导出和受控`/api/v1/exports/{id}/download`接口，允许JSON、Markdown、PDF、DOCX、PPTX。核对发起origin、具体顶层frame、完整URL链和文件名；不允许可执行扩展名、路径、设备名或双向文本控制符。保存位置由Electron系统保存对话框选择，覆盖已有文件需确认，保存后不自动打开文件。没有向页面暴露文件路径或写文件API。
- 远端视频/图片与外链策略、完整语音识别服务集成仍待验收。权限放行不代表语音模型、全部导出生成器或所有媒体能力已经通过。
- Electron sandbox不替代题目代码执行隔离：独立代码worker origin、资源限制、完整IPC安全审计仍未完成。

桌面宿主采用固定版本 Electron、electron-builder 和现有 Python 控制器，没有增加更新器、遥测或另建课程/记忆实现。桌面前端由既有 FastAPI 与 API 同源托管，运行时无需 Vite preview 或额外前端进程；最终分发构建、全部服务携带和干净机器验收仍待完成。

## 独立前端入口

把已有前端构建产物放入分发目录，例如 `C:/EduNova/app/frontend`，包含 `index.html`、`assets/` 和 `pyodide/`。只复制公开的构建产物，不复制仓库源码、`.env` 或 `node_modules`。在受控 API 服务环境中设置绝对路径：

```json
{
  "name": "api",
  "command": ["C:/EduNova/runtime/python/python.exe", "-m", "uvicorn", "backend.app.desktop_app:create_app", "--factory", "--host", "127.0.0.1", "--port", "18000"],
  "env": {"EDUNOVA_DESKTOP_FRONTEND_DIR": "C:/EduNova/app/frontend"},
  "health_url": "http://127.0.0.1:18000/api/health"
}
```

这是完整服务清单中的 API 条目示例，不含数据库初始化、凭据和队列配置。窗口 URL 同步设为 `http://127.0.0.1:18000/login`，删除原有 Vite preview 服务条目；前端构建应使用同源 `/api/v1`。

入口复用安装版本已有的 `FastAPI.frontend()`，由框架处理文件读取、MIME、ETag、范围请求和浏览器路由回退；`/assets`、`/pyodide` 缺失文件保持 404。薄 ASGI 适配仅把 `/api`、API 文档、OpenAPI、WebSocket 和生命周期请求交还原有后端，避免 API 的 401/404/405 被单页应用回退替换。原来的 `backend.app.main:app` 仍是 API-only 入口，容器部署不变。

目录未配置、路径非绝对或构建文件缺失时启动失败。该入口不生成构建产物，也不下载资源；验证命令：`python -m pytest backend/tests/test_desktop_app.py backend/tests/test_health.py -q`。

## 验证

`npm.cmd test --prefix desktop` 验证IPC、麦克风来源/种类/确认失效、导出frame/来源/重定向/文件名边界。真实窗口验证入口在本机忽略目录 `.planning/desktop-feasibility/probe_electron_stack.py`，复用已有学习闭环测试正文，采用私有PostgreSQL/Redis/RQ数据与受控生成夹具；不是外部模型质量或缓存性能测量。

媒体与导出驱动使用Chromium模拟音频，自动回答权限确认并把保存位置定向到试验目录。这些替代行为仅存在于忽略目录的验收脚本，不进入桌面源码；不能据此宣称真实麦克风硬件、人工点击系统保存/覆盖对话框或所有格式生成已经验收。

源码许可与版本依据：Electron MIT；Chromium/Node及捆绑内容须单独保留第三方通知。npm audit只覆盖npm树，不证明整个Chromium二进制无漏洞。正式分发前仍须审计最终完整依赖包。
