# Windows 桌面运行控制器

`scripts/desktop_runtime.py` 使用 `backend/requirements-desktop.txt` 中的 pywin32，管理可信本地 manifest 定义的 Windows 服务，不下载依赖。Electron 管理窗口，打包入口生成安装器；Linux/Docker 依赖不变。

## 调用约定

```powershell
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py start --manifest C:/EduNova/runtime.json
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py status --manifest C:/EduNova/runtime.json
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py stop --manifest C:/EduNova/runtime.json --wait-seconds 60
```

`start` **保持前台运行**，由桌面主进程持有；在另一终端或宿主中调用 `stop`。输出 `phase=running` 才表示启动检查完成，不能以命令退出或保存 PID 判断就绪。

`status` 的 `active` 来自内核互斥量，状态文件只保存上次记录；旧 PID 不用于终止进程。关闭后保留 `phase=stopped` 和清理结果。状态、日志使用 UTF-8；manifest、状态、日志及数据库写入用户数据目录，不写只读安装目录。

## Manifest 合同

示例仅说明结构，须替换为已准备且通过分发审核的运行时，不能直接启动完整系统。

```json
{
  "state_file": "state.json",
  "services": [
    {
      "name": "api",
      "command": ["C:/EduNova/runtime/python/python.exe", "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "18000"],
      "cwd": "data",
      "env": {"PYTHONUTF8": "1", "PYTHONPATH": "C:/EduNova/app"},
      "health_url": "http://127.0.0.1:18000/api/health",
      "timeout": 30,
      "log": "logs/api.log"
    }
  ]
}
```

- `command`：不经 shell 的参数数组，首项须为存在的绝对可执行路径，参数可为空字符串。仅接受可信本地 manifest，不执行远端上传命令。
- `cwd`：相对 manifest 目录解析，默认该目录；使用隔离数据目录，避免读取仓库 `.env`。
- `env`：覆盖环境变量，值为 `null` 时移除；模板与日志不得含真实密钥。
- `port`：可选 TCP 端口，也可由 HTTP `health_url` 推导。Windows 排他绑定预检，占用即失败，不终止占用者或换端口。
- `health_url`：只接受显式端口的 `http://127.0.0.1`，不走系统代理、不跟随重定向。
- `ready_command`：可选依赖探针，优先于 HTTP，退出码 0 表示就绪；与服务同属受控进程组，受启动期限约束。
- `mode: oneshot`：用于创建专用数据库、迁移等一次性步骤；成功退出后才继续后续服务。
- `stop_command`：可选组件正常关闭命令，例如 PostgreSQL 的 `pg_ctl ... -m fast -w stop`、Redis shutdown 和 RQ shutdown。`stop_timeout` 默认 15 秒，超时会回收本服务进程组；结果明确标记 `graceful=false`。
- 按列表顺序启动并等待就绪，反向关闭；无探针时只检查进程存活，不代表依赖健康。

## 实现选择

复用 Windows RQ 原型的 pywin32/Windows Job Object，不引入进程管理平台。包装进程先加入 kill-on-close Job，再经父进程许可启动命令。控制器持有 Job 句柄并监控进程，崩溃时由 Windows 回收普通后代；此机制控制生命周期，不是代码安全沙箱。

互斥量按规范化状态路径命名，防止同一登录会话的两个控制器并管配置。停止通过命名事件通知持有者，不按 PID 执行 taskkill；不提供跨登录会话或同账户恶意进程隔离。

官方依据：
- Windows Job Objects：https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- pywin32 Job API：https://mhammond.github.io/pywin32/win32job.html
- pywin32 event/mutex API：https://mhammond.github.io/pywin32/win32event.html

## 验证入口与范围

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_desktop_runtime.py -q
```

Windows 专属测试验证中文/空格目录、同时启动互斥、保留无关端口占用者、部分启动失败回滚、控制器/服务异常退出、子孙进程回收、陈旧 PID 不操作无关进程、就绪超时、启动中取消、关闭命令超时和无效 manifest。其他平台跳过这些 Windows 边界用例。

生命周期测试不替代安装兼容性、跨版本升级或备份恢复验证。无专用关闭命令时使用进程组回收，不代表正常退出；版本限制见[发布说明](RELEASE_NOTES_0.1.0.md)。

## 宿主生命周期桥

`scripts/desktop_host_bridge.py --manifest <可信本地配置>` 提供 JSON-lines stdin/stdout。manifest、Python 与 controller 路径仅由可信启动参数指定，不接受消息传入。Electron 主进程另行校验发送者、主 frame 和 origin，只暴露固定 preload 方法；管道不替代 renderer 安全边界。

请求如 `{"id":"1","method":"start"}`，仅接受 `id` 和 `method`，方法为 `start/status/stop`，每条最多 4096 字符。结果如 `{"id":"1","ok":true,"result":{"phase":"running"}}`；错误保留合法 ID，畸形 JSON 使用空 ID。状态只返回 active/phase/owned，不返回路径、PID、环境或原始日志。

start 持有常驻控制器、等待其就绪，重复调用对自有已运行实例幂等；stop 只关闭自有实例。命令顺序处理，启动中取消需断开宿主管道，不支持并发 RPC。

`--host-stdin` 在管道 EOF 时请求反向关闭服务，桥正常或异常退出均触发清理。超出关闭期限时终止自有控制器 Popen 对象，由 Job Objects 回收服务；超时兜底不保证数据库正常退出，须验证恢复。

验证入口：`python -m pytest backend/tests/test_desktop_host_bridge.py backend/tests/test_desktop_runtime.py -q`，覆盖消息合同、启停、异常断开和服务清理。

## Electron 窗口与权限

窗口配置与启动见[桌面 README](../desktop/README.md)。状态 IPC、麦克风确认与受控导出仅接受自有主窗口的匹配来源；拒绝摄像头、子 frame 和外来来源，导航或刷新使确认失效。页面无通用写文件接口，位置选择与覆盖确认由系统对话框处理。

权限和打包边界检查入口为 `node --test desktop/test/*.test.cjs`。自动化检查不能替代真实硬件和人工对话框操作验证。

## 桌面静态前端与 API 同源

桌面 API 服务可以改用 `backend.app.desktop_app:create_app --factory`，并以 `EDUNOVA_DESKTOP_FRONTEND_DIR` 指向分发目录中的前端构建产物。窗口与 API 使用同一个 `127.0.0.1` 端口，manifest 中不再需要单独的 Vite preview 服务。示例见 `desktop/README.md`。

桌面入口复用 FastAPI 的 `frontend()` 和 Starlette 静态文件处理，无需随包运行 Vite preview 或额外反向代理。Docker 部署继续使用 Nginx 和容器网络。

适配只处理入口配置与请求边界，保留 API 鉴权、错误、流式响应、业务状态和 OpenAPI。frontend 只能指向公开构建产物，不得指向数据库、上传、配置或源码目录。请求仍受 Electron 同源与回环监听限制，无新增外部端点；跨版本升级和系统隔离须另验。

验证覆盖：中文/空格构建目录，登录与深层路由刷新，JS/MIME、ETag/304、HEAD、WASM/范围请求，API 401/404/405、OpenAPI 与流式内容，缺失资源及路径越界请求，缺失构建的启动失败。安装和分发要求见[桌面分发说明](DESKTOP_DISTRIBUTION.md)。

官方依据：[FastAPI Frontend](https://fastapi.tiangolo.com/tutorial/frontend/)、[Starlette StaticFiles](https://starlette.dev/staticfiles/)、[Vite 静态部署](https://vite.dev/guide/static-deploy.html)。
