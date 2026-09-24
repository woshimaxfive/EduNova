# 本地语音输入与浏览器朗读

语音输入使用 **SenseVoice Small INT8 + Sherpa-ONNX 1.13.8**，在部署 EduNova 的机器上运行。朗读使用访问者浏览器提供的**本地中文声音**，不上传回答文本进行合成。两项均无需语音 Key；主模型和图片配置不变。

## 启动与迁移

Windows 运行 `02_Start_EduNova.bat`。启动脚本构建识别服务、准备固定版本权重、校验SHA256，并在断网容器验证公开录音和静音处理；成功后清理旧 `SYSTEM_SPEECH_*` 配置。保留主模型和学习数据。

首次下载约238MB的SenseVoice模型及配套文件。脚本 `scripts/prepare_local_speech.py` 不再下载Kokoro，服务也不再加载TTS模型。已有Kokoro缓存不会自动删除用户文件；确认不再使用后可单独清理 `storage/models/speech/kokoro`。模型、录音和.env均不得入Git。

手动准备：`powershell -File scripts/prepare_local_runtime.ps1`，然后运行语音配置迁移脚本和 `docker compose up -d --build`。非Windows可以在已有huggingface-hub/httpx环境运行相同Python准备脚本。

## 使用

- **语音输入**：浏览器需HTTPS或localhost及麦克风权限，最多60秒；录音送往你部署的EduNova识别服务。结果填入输入框，检查同音字和术语后再发送，不自动提交。
- **朗读**：仅选择 `localService=true` 的中文声音，优先zh-CN；等待异步声音列表，按句分段，支持暂停、继续、停止。停止或离开页面后不继续播放下一段。
- **缺少声音**：提示在系统安装中文语音包，可尝试Chrome/Edge；不选择在线或未指定的默认声音，不回退云端，也不回退服务器TTS。不同设备的音色和可用性可能不同。
- **识别失败**：服务繁忙429、空识别422、服务不可用503、超时504明确返回，不使用浏览器云识别。识别容器使用内部隔离网络、只读模型挂载，不保存录音。
- **旧客户端**：`POST /api/v1/speech/synthesis` 保留鉴权，固定返回410和 `SPEECH_SYNTHESIS_RETIRED`，提示刷新前端；不再返回WAV。转写接口不变。

## 实测和边界

当前Windows Chromium检测到微软Huihui、Kangkang和Yaoyao三个本地中文声音。Huihui首次onstart约1.65秒，后续三次约28–36毫秒；这是单轮浏览器事件计时，不是声学测量，也不代表其他电脑表现或音质排名。原Kokoro三句合成约3–10秒，用户试听后选择浏览器方案。

浏览器zh-CN本地识别能力检查返回downloadable，语言包未安装，因此仍保留已验证的SenseVoice。SenseVoice公开录音和静音检查通过，但专业术语、同音字和中英混读仍需核对；没有完成大样本真人录音验收。

## 复用与许可

复用Web Speech API，不新增前端语音库。识别继续复用现有PCM转换、权限、Sherpa适配和内部容器，不改变LangGraph、引用、评分、掌握度或事务逻辑。

SenseVoice模型卡指向FunASR MODEL_LICENSE 1.1，不是Apache；准备脚本保留固定版本模型许可。Sherpa-ONNX仓库为Apache-2.0，但1.x预编译包仍包含espeak-ng/piper相关GPL组件：即使不再使用TTS，也不能把整个运行时称为纯MIT/Apache。再分发二进制镜像前需核对许可证、对应源码等义务；本仓库不发布预构建语音镜像。

来源：[浏览器本地声音标识](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService)、[SenseVoice](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)、[固定模型许可](https://github.com/modelscope/FunASR/blob/3ff9259aade4f7e4360645df28cad8f81959ee91/MODEL_LICENSE)、[Sherpa许可说明](https://github.com/k2-fsa/sherpa-onnx/issues/3731)。
