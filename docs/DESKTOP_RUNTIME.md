# Windows 桌面运行控制器

`scripts/desktop_runtime.py` 管理可信本地 manifest 中的服务，当前支持 Windows，使用 `backend/requirements-desktop.txt` 中独立固定的 pywin32。Linux/Docker 后端依赖不变。控制器只负责服务生命周期；窗口由 Electron 宿主管理，安装器由独立打包入口生成。控制器不会自动下载依赖。

## 调用约定

```powershell
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py start --manifest C:/EduNova/runtime.json
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py status --manifest C:/EduNova/runtime.json
.venv/Scripts/python.exe -X utf8 scripts/desktop_runtime.py stop --manifest C:/EduNova/runtime.json --wait-seconds 60
```

`start` **保持前台运行**，供桌面主进程持有；在另一终端或桌面主进程中调用 `stop`。开始后输出 `phase=running` 才代表所有启动检查完成。不要沿用初版“启动命令退出、仅保存 PID”的假设。

`status` 的 `active` 来自内核互斥量；状态文件只是上次运行记录。即便状态文件留下旧 PID，停止命令也不会据此终止进程。正常关闭后保留 `phase=stopped` 及清理结果，便于诊断。状态与日志均使用 UTF-8；manifest、状态、日志和可写数据库应位于用户数据目录，不能写入只读安装目录。

## Manifest 合同

示例中的路径仅说明结构，需要替换成已准备且通过分发审核的本地运行时。它不是可直接启动完整 EduNova 的预设。

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

- `command`：参数数组，首项是实际存在的绝对可执行路径；不经 shell 解释。参数允许空字符串。manifest 是可信本地配置，不能接受远端上传的任意命令。
- `cwd`：相对 manifest 目录解析，默认该目录；显式选择隔离数据目录以避免无意读取仓库 `.env`。
- `env`：覆盖环境变量；值为 `null` 时移除该变量。不要把真实密钥写入可提交的模板或日志。
- `port`：可选 TCP 端口，启动前以 Windows 排他绑定预检；HTTP `health_url` 可自动提供端口。占用时明确失败，不终止原占用者、不擅自切换端口。
- `health_url`：只接受显式端口的 `http://127.0.0.1`，不走系统代理、不跟随重定向。
- `ready_command`：可选真实依赖探针，退出码 0 表示就绪；优先于 HTTP。与服务同属受控进程组，并受启动期限约束。
- `mode: oneshot`：用于创建专用数据库、迁移等一次性步骤；成功退出后才继续后续服务。
- `stop_command`：可选组件正常关闭命令，例如 PostgreSQL 的 `pg_ctl ... -m fast -w stop`、Redis shutdown 和 RQ shutdown。`stop_timeout` 默认 15 秒，超时会回收本服务进程组；结果明确标记 `graceful=false`。
- 服务按列表顺序启动并等待就绪，反向关闭。没有就绪探针的服务只检查进程存活，不能宣称依赖健康。

## 实现选择

复用现有 Windows RQ 原型已采用的 pywin32/Windows Job Object，不引入新进程管理平台。每个服务先进入等待父进程许可的包装进程，加入 kill-on-close Job 后才启动实际命令；控制器持有 Job 句柄并持续监控进程。控制器崩溃时 Windows 回收其 Job 中的普通后代进程；这是生命周期控制，不是代码执行的安全沙箱。

命名内核互斥量按规范化状态路径派生，用于同一登录会话内防止两个控制器同时管理同一配置。停止通过命名事件请求当前持有者执行，而非读取 PID 后执行 taskkill。该范围不代表多 Windows 登录会话或恶意同账户进程之间的安全隔离。

官方依据：
- Windows Job Objects：https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- pywin32 Job API：https://mhammond.github.io/pywin32/win32job.html
- pywin32 event/mutex API：https://mhammond.github.io/pywin32/win32event.html

## 验证入口与范围

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_desktop_runtime.py -q
```

Windows 专属测试验证中文/空格目录、同时启动互斥、保留无关端口占用者、部分启动失败回滚、控制器/服务异常退出、子孙进程回收、陈旧 PID 不操作无关进程、就绪超时、启动中取消、关闭命令超时和无效 manifest。其他平台跳过这些 Windows 边界用例。

服务生命周期测试不替代安装器兼容性、跨版本升级和备份恢复验证。未配置专用正常关闭命令的服务使用进程组回收，不能将其表述为正常退出。版本限制见[发布说明](RELEASE_NOTES_0.1.0.md)。

## 宿主生命周期桥

`scripts/desktop_host_bridge.py --manifest <可信本地配置>` 提供 JSON-lines stdin/stdout 合同。manifest、Python与controller路径只能由可信宿主启动参数指定，不能由消息传入。Electron主进程已接入此管道，并独立验证发送者/主frame/origin，只暴露固定preload方法；管道本身不替代renderer安全边界。

请求示例：`{"id":"1","method":"start"}`。仅接受 `id` 和 `method`，方法仅为 `start/status/stop`，单消息至多4096字符。结果为 `{"id":"1","ok":true,"result":{"phase":"running"}}`；错误沿用合法请求ID，畸形JSON返回空ID。状态只返回active/phase/owned，不向窗口返回本地路径、PID、环境或原始日志。

start持有常驻控制器进程并等待它自己的就绪消息；重复start对自己持有的已运行实例幂等。stop只关闭本桥持有实例，不操作另一宿主的控制器。命令按接收顺序处理，启动中如需取消应断开宿主管道；这不是并发RPC服务器。

控制器新增 `--host-stdin`：管道EOF请求反向关闭服务。桥正常退出关闭拥有的控制器管道；桥突然退出也会使管道EOF，控制器自行清理。如果关闭超过桥期限，会终止其持有的控制器Popen对象，借助已有Job Objects回收服务。该超时兜底不承诺数据库正常退出，须保留恢复验收。

验证入口：`python -m pytest backend/tests/test_desktop_host_bridge.py backend/tests/test_desktop_runtime.py -q`，覆盖消息合同、启停、异常断开和服务清理。

## Electron 窗口与权限

窗口配置和启动命令见 [桌面 README](../desktop/README.md)。宿主提供状态 IPC、麦克风确认和受控导出，只接受自有主窗口及匹配来源的请求。摄像头、子 frame 和外来来源请求被拒绝；导航或刷新会使相关确认失效。页面没有通用文件写入接口，保存位置与覆盖确认由系统对话框处理。

权限和打包边界检查入口为 `node --test desktop/test/*.test.cjs`。自动化检查不能替代真实硬件和人工对话框操作验证。

## 桌面静态前端与 API 同源

桌面 API 服务可以改用 `backend.app.desktop_app:create_app --factory`，并以 `EDUNOVA_DESKTOP_FRONTEND_DIR` 指向分发目录中的前端构建产物。窗口与 API 使用同一个 `127.0.0.1` 端口，manifest 中不再需要单独的 Vite preview 服务。示例见 `desktop/README.md`。

桌面入口复用 FastAPI 的 `frontend()` 和 Starlette 静态文件处理，无需随包运行 Vite preview 或额外反向代理。Docker 部署继续使用 Nginx 和容器网络。

适配代码仅负责桌面入口配置和请求边界。API 原有鉴权、错误状态、流式响应、业务状态和 OpenAPI 保持原实现；静态文件属于公开构建产物，不允许把数据库、上传目录、配置或源码目录作为 frontend 目录。全部请求仍由现有 Electron 同源策略与回环监听约束，无新增外部网络端点。跨版本升级和完整系统隔离需要单独验证。

验证覆盖：中文/空格构建目录，登录与深层路由刷新，JS/MIME、ETag/304、HEAD、WASM/范围请求，API 401/404/405、OpenAPI 与流式内容，缺失资源及路径越界请求，缺失构建的启动失败。安装和分发要求见[桌面分发说明](DESKTOP_DISTRIBUTION.md)。

官方依据：[FastAPI Frontend](https://fastapi.tiangolo.com/tutorial/frontend/)、[Starlette StaticFiles](https://starlette.dev/staticfiles/)、[Vite 静态部署](https://vite.dev/guide/static-deploy.html)。
