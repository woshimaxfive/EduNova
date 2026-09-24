# 本地语音输入与浏览器朗读

语音输入使用 **SenseVoice Small INT8 + Sherpa-ONNX 1.13.8**，在部署 EduNova 的机器上运行。朗读使用访问者浏览器提供的**本地中文声音**，不上传回答文本进行合成。两项均无需语音 Key；主模型和图片配置不变。

## 启动与迁移

安装与启动统一按[部署指南](DEPLOYMENT.md)操作。语音模型准备包含固定版本权重、SHA256校验与断网推理检查；旧 `SYSTEM_SPEECH_*` 配置由迁移脚本清理。

首次下载约238MB的SenseVoice模型及配套文件。脚本 `scripts/prepare_local_speech.py` 不再下载Kokoro，服务也不再加载TTS模型。已有Kokoro缓存不会自动删除用户文件；确认不再使用后可单独清理 `storage/models/speech/kokoro`。模型、录音和.env均不得入Git。

非Windows可以在已有huggingface-hub/httpx环境运行 `scripts/prepare_local_speech.py` 准备模型，再按部署指南配置服务。

## 使用

- **语音输入**：浏览器需HTTPS或localhost及麦克风权限，最多60秒；录音送往你部署的EduNova识别服务。结果填入输入框，检查同音字和术语后再发送，不自动提交。
- **朗读**：仅选择 `localService=true` 的中文声音，优先zh-CN；等待异步声音列表，按句分段，支持暂停、继续、停止。停止或离开页面后不继续播放下一段。
- **缺少声音**：提示在系统安装中文语音包，可尝试Chrome/Edge；不选择在线或未指定的默认声音，不回退云端，也不回退服务器TTS。不同设备的音色和可用性可能不同。
- **识别失败**：服务繁忙429、空识别422、服务不可用503、超时504明确返回，不使用浏览器云识别。识别容器使用内部隔离网络、只读模型挂载，不保存录音。
- **旧客户端**：`POST /api/v1/speech/synthesis` 保留鉴权，固定返回410和 `SPEECH_SYNTHESIS_RETIRED`，提示刷新前端；不再返回WAV。转写接口不变。

## 使用边界

识别结果中的专业术语、同音字和中英混读需要用户核对。浏览器中文声音的可用性、音色与启动速度取决于访问者的设备和系统语音包；本地识别服务不依赖浏览器安装识别语言包。

## 复用与许可

复用Web Speech API，不新增前端语音库。识别继续复用现有PCM转换、权限、Sherpa适配和内部容器，不改变LangGraph、引用、评分、掌握度或事务逻辑。

SenseVoice模型卡指向FunASR MODEL_LICENSE 1.1，不是Apache；准备脚本保留固定版本模型许可。Sherpa-ONNX仓库为Apache-2.0，但1.x预编译包仍包含espeak-ng/piper相关GPL组件：即使不再使用TTS，也不能把整个运行时称为纯MIT/Apache。再分发二进制镜像前需核对许可证、对应源码等义务；本仓库不发布预构建语音镜像。

来源：[浏览器本地声音标识](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService)、[SenseVoice](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)、[固定模型许可](https://github.com/modelscope/FunASR/blob/3ff9259aade4f7e4360645df28cad8f81959ee91/MODEL_LICENSE)、[Sherpa许可说明](https://github.com/k2-fsa/sherpa-onnx/issues/3731)。
