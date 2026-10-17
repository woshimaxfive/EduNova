# Electron Windows 桌面客户端

Electron 桌面宿主复用 EduNova 前端。安装与数据说明见[桌面分发说明](../docs/DESKTOP_DISTRIBUTION.md)，本文面向源码构建与维护。

## 安装器构建

构建使用 electron-builder 26.15.3，入口为 `npm.cmd run pack:check --prefix desktop`、`pack:dir` 和 `dist`。`EDUNOVA_PAYLOAD_DIR` 须指向独立资源目录的绝对路径。清单完整、逐文件哈希匹配且分发材料核对通过后才生成安装器，不自动发布。

`scripts/assemble_desktop_payload.py` 按白名单组装已验证运行时与当前源码，拒绝覆盖旧目录，默认 `redistributionReviewed=false`。它依赖本机资产，尚不能从全新开发环境下载并重建全部依赖。

分发核对未完成时，`node desktop/packaging.cjs --local-test` 可生成本机试装包，单独输出到 `desktop/dist/local-test`，不代表正式分发通过。构建使用 `BCJ` 过滤器，避免旧 NSIS 解压器跳过自动 ARM64 过滤的辅助二进制。过深的 Python 许可证路径迁至 `notices/python`，保留原字节；原路径、安装路径和哈希记入 `notices/relocated-license-paths.json`，不得删许可证规避长路径。

安装器面向当前用户，不提权，创建快捷方式，卸载保留数据，安装后不自动启动。首次运行由随包 `desktop_prepare.py` 在 `%APPDATA%/EduNova` 准备凭据、数据库、配置加密密钥、上传目录和窗口 profile；安装目录只提供程序与模型。开发态使用下方显式配置。

AppData 可能被重定向；准备程序按物理目录核对 profile，接受同一目录的逻辑/重定向路径，拒绝不同数据目录。

首次启动接入数据库初始化/迁移、Redis、离线语音、API、Windows RQ worker、搜索与独立代码执行。候选检查与实际安装验收分别记录，清单生成成功不等于完整交付。

## 运行

```powershell
npm.cmd ci --prefix desktop
node desktop/node_modules/electron/install.js
$env:EDUNOVA_DESKTOP_CONFIG = 'C:/EduNova/desktop.json'
npm.cmd start --prefix desktop
```

Electron 44.4.5 需显式安装二进制；第二条命令按随包 checksums 校验运行时。Node 要求 >=22.12.0。开发运行时不作为最终交付包。

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

URL 须与 manifest 中带健康探针的回环服务同源。示例需另行准备原生服务与模型，不是完整分发配置。勿提交凭据、用户 profile 或本机 manifest；控制器合同见[桌面运行时](../docs/DESKTOP_RUNTIME.md)。

## 行为与边界

- 启动页等待 Python 宿主桥启动服务，成功后加载前端。
- 关窗时先断开桥、清理后台服务，再退出 Electron；主进程异常退出也由管道 EOF 触发清理。
- 同一 userData 的第二实例聚焦已有窗口；隔离试验须使用独立 profile。
- renderer 启用 sandbox/contextIsolation/webSecurity，关闭 Node/webview，只暴露 status/quit。主进程核对自有 webContents、顶层 frame、精确 origin，拒绝多余 IPC 参数。
- 拒绝弹窗、跨 origin 导航/重定向、远端请求和未授权权限，页面不能发送任意命令。
- 麦克风只接受本窗口同源顶层页的纯音频请求，默认拒绝，须弹窗确认。确认仅限当前文档，刷新或重开需再问；等待时导航使请求失效。拒绝摄像头、屏幕录制、子页面与外来来源，系统权限仍由 Windows 控制。
- Blob 与受控 `/api/v1/exports/{id}/download` 允许导出 JSON、Markdown、PDF、DOCX、PPTX。核对 origin、顶层 frame、完整 URL 链及文件名，拒绝可执行扩展名、路径、设备名和双向文本控制符。系统对话框选择位置，覆盖须确认，保存后不自动打开；页面无文件路径或通用写入 API。
- 远端视频/图片与外链策略、真实麦克风和完整语音体验仍需验收；权限测试不能证明所有语音、导出或媒体能力可用。
- Electron sandbox 不替代题目代码隔离；独立代码 worker origin、资源限制与完整 IPC 安全审计仍未完成。

宿主使用固定版本 Electron、electron-builder 与既有 Python 控制器，无更新器、遥测或独立课程/记忆实现。FastAPI 同源托管前端，无需 Vite preview 或额外前端进程。[0.1.0 安装包已发布](https://github.com/woshimaxfive/EduNova/releases/tag/v0.1.0-desktop-source-preview)；后续构建仍需核对完整载荷并验收，干净 Windows 等未验证项见[版本说明](../docs/RELEASE_NOTES_0.1.0.md)。

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

入口复用 `FastAPI.frontend()` 处理文件、MIME、ETag、范围请求与页面路由回退；`/assets`、`/pyodide` 缺失仍返回 404。ASGI 适配将 `/api`、API 文档、OpenAPI、WebSocket 和生命周期请求交回后端，保留 401/404/405。容器仍使用 API-only 的 `backend.app.main:app`。

目录未配置、路径非绝对或构建文件缺失时启动失败。该入口不生成构建产物，也不下载资源；验证命令：`python -m pytest backend/tests/test_desktop_app.py backend/tests/test_health.py -q`。

## 验证

`npm.cmd test --prefix desktop` 验证 IPC、麦克风权限及导出来源、重定向和文件名边界。

自动化权限检查不能替代真实麦克风、系统保存对话框及导出文件的人工验证。

Electron 采用 MIT，Chromium/Node 及捆绑组件另须保留第三方通知。npm audit 仅覆盖 npm 树，不证明 Chromium 二进制无漏洞；正式分发须检查完整依赖包。
