# 本地语音输入与浏览器朗读

语音输入使用 SenseVoice Small INT8 + Sherpa-ONNX 1.13.8，在部署机器上识别。朗读使用浏览器本地中文声音，不上传回答文本。两项无需语音 Key，不改变主模型与图片配置。

## 启动与迁移

安装与启动统一按[部署指南](DEPLOYMENT.md)操作。语音模型准备包含固定版本权重、SHA256校验与断网推理检查；旧 `SYSTEM_SPEECH_*` 配置由迁移脚本清理。

首次下载约 238 MB 模型及配套文件。`scripts/prepare_local_speech.py` 不下载 Kokoro，服务不加载 TTS；旧缓存不会自动删除，确认不用后可清理 `storage/models/speech/kokoro`。模型、录音与 .env 不得进入 Git。

非 Windows 环境需安装 huggingface-hub/httpx，运行 `scripts/prepare_local_speech.py` 后按部署指南配置服务。

## 使用

- **语音输入**：需 HTTPS 或 localhost 及麦克风权限，最多 60 秒；录音发给所部署的识别服务。结果填入输入框，核对后手动发送。
- **朗读**：只选 `localService=true` 的中文声音，优先 zh-CN；异步等待声音列表，按句播放，可暂停、继续或停止。停止或离页不再播下一段。
- **缺少声音**：提示安装系统中文语音包，可尝试 Chrome/Edge；不选择在线或未指定的默认声音，不回退云端或服务器 TTS。音色与可用性因设备而异。
- **识别失败**：繁忙 429、空结果 422、不可用 503、超时 504 明确返回，不使用浏览器云识别。容器采用内部隔离网络、只读模型挂载，不保存录音。
- **旧客户端**：`POST /api/v1/speech/synthesis` 保留鉴权，返回 410/`SPEECH_SYNTHESIS_RETIRED`，提示刷新，不返回 WAV；转写接口不变。

## 使用边界

术语、同音字与中英混读需人工核对。朗读可用性、音色和启动速度取决于设备及系统语音包；本地识别不依赖浏览器识别语言包。

## 复用与许可

朗读复用 Web Speech API，无需新前端库；识别复用 PCM 转换、权限、Sherpa 适配与内部容器，不改变 LangGraph、引用、评分、掌握度或事务。

原始 SenseVoice 模型卡指向 FunASR MODEL_LICENSE 1.1，社区粤语转换/微调权重另有声明，脚本保留固定版本许可。Sherpa-ONNX 仓库为 Apache-2.0，但 1.x 预编译包含 espeak-ng/piper 相关 GPL 组件；停用 TTS 不改变其分发义务，不能将整套运行时称为纯 MIT/Apache。再分发二进制镜像前须核对许可证与对应源码；本仓库不发布预构建语音镜像。

## 模型配置与分发

准备脚本保留两种显式用途，不会自动覆盖已有本地权重：

| 用途 | 模型仓库与固定修订 | 配置入口 |
| --- | --- | --- |
| 本地 / Docker 默认 | `csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09`，`355f4d4884d8afd08aef04b9007a8556d7b463b2` | `MODELS`；默认模型目录 |
| 桌面分发 | `csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`，`2365baeacb507f821a0c8120fcee3d484dba7a07` | `RELEASE_MODELS`；`--release-model --model-dir <独立目录>` |

桌面来源及摘要见 `desktop/release-model-assets.lock.json`；`desktop/model-assets.lock.json` 对应本地准备资产，不能替代桌面分发清单。脚本拒绝将分发模型直接写入默认本地目录。

2025 转换权重的适用分发许可链仍需单独核对。2024 转换仓库提供明确的 LICENSE 指针；随包仍须保留模型许可和实际运行时组件要求的材料。模型选择不意味着其推理运行时的所有捆绑组件采用同一许可证。

来源：[模型准备脚本](../scripts/prepare_local_speech.py)、[桌面模型清单](../desktop/release-model-assets.lock.json)、[第三方声明](../THIRD_PARTY_NOTICES.md)。
