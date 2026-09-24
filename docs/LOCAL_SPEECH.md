# 本地语音输入与朗读

默认启动包含独立 `speech` 服务：Sherpa-ONNX 1.13.8 在 CPU 上运行 SenseVoice int8 识别与 Kokoro 1.1 中文 int8 朗读。无需语音 Key、GPU 或宿主机 Python。主模型仍按自己的配置运行，识图跟随主模型。

## 启动与迁移

Windows 运行 `02_Start_EduNova.bat`。它先构建运行时、下载固定版本权重、校验 SHA256，并在无网络容器中验证语音，成功后才移除 `.env` 中旧 `SYSTEM_SPEECH_*` 配置并启动服务。主模型凭证和学习数据不受影响。手动准备可运行 `powershell -File scripts/prepare_local_runtime.ps1`，再执行 `scripts/migrate_local_speech_env.ps1` 和 `docker compose up -d --build`。

首次准备需要访问 Hugging Face/PyPI；之后权重保存在忽略的 `storage/models/speech`，通过校验则复用。下载脚本为 `scripts/prepare_local_speech.py`，其他系统可在已有 Python 环境安装 huggingface-hub/httpx 后运行同一脚本。不要提交模型缓存、录音、`.env` 或个人数据。

语音权重及词典约453MB，另有推理依赖和镜像层。服务限制2核、1536MiB内存；正式服务一次短句合成后约613MiB，测试期间容器曾达到约1.09GiB，不是整套系统的实际占用。模型常驻内存以避免每次重新加载，Docker仍建议至少分配8GB内存。

## 使用与边界

- 语音输入需要浏览器麦克风授权及 HTTPS 或 localhost。最多录制60秒；识别结果填入输入框，可检查修改后再发送。
- 朗读使用本地生成的 WAV，前端每段最多40字符并预取下一段；支持停止与暂停。公共合成接口每次最多180字符，长文本须分段。
- 推理服务仅连接内部隔离网络，不暴露宿主端口、不接收模型Key。音频在内存中处理；接口不保存录音或朗读文件。反向代理和业务接口仍保留登录校验。
- 同时只运行一项推理；忙时返回429，超时/服务故障明确报错，不调用旧讯飞服务、浏览器云识别或在线声音。客户端超时不强行终止已经开始的本地推理。
- 本地不代表即时或云端同等质量。2核容器内一条约20字的中文合成回测约3.7秒、识别约0.25秒；108字合成曾耗时35秒。硬件、文本和负载都会影响等待时间，长段之间可能停顿。
- 现有样例能保留“数据结构”“先进先出”，但出现“队列→对列”等同音错误，专业术语和中英混读仍需人工核对。没有完成大样本真人录音、主观音质或多人并发质量验收。

## 选型与许可

复用现有录音、PCM转换、鉴权和播放链路，只为成熟推理引擎增加适配与内部服务，不改LangGraph、权限、引用、评分及掌握度逻辑。比较过Sherpa-ONNX统一推理、Faster-Whisper搭配独立TTS、Piper；后两者分别增加第二套推理运行时或存在当前GPL版本与中文模型适配成本。LangChain/LlamaIndex音频封装不能替代实际本地语音引擎。

MeloTTS int8约74MB、短句更快，但同一合成再识别样例将“队列遵循先进先出”识别为明显不同词语，未通过当前回归，因此未选用。合成再识别只能作为烟测，不能单独判定声音自然度或把错误归因到某个模型。

SenseVoice使用上游模型卡指向的 **FunASR MODEL_LICENSE 1.1**，不是Apache-2.0；准备脚本保留固定版本许可。Kokoro模型声明Apache-2.0，但其语音运行时包含其他许可组件。Sherpa-ONNX仓库为Apache-2.0，**当前1.x预编译包包含espeak-ng/piper相关GPL组件**，不能将整个语音镜像称为纯MIT/Apache。仅以独立服务部署不自动消除分发义务；再分发二进制镜像前，需核对并提供相应组件的许可证和对应源码等材料。目前仓库分发源码、构建配方和下载脚本，不发布预构建语音镜像。

来源：[Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)、[上游1.x许可说明](https://github.com/k2-fsa/sherpa-onnx/issues/3731)、[SenseVoice模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)、[固定模型许可](https://github.com/modelscope/FunASR/blob/3ff9259aade4f7e4360645df28cad8f81959ee91/MODEL_LICENSE)、[Kokoro权重](https://huggingface.co/csukuangfj/kokoro-int8-multi-lang-v1_1)。固定revision和权重校验值见准备脚本。已查询固定推理包的OSV记录，未发现已知公告；这不代表完整供应链审计。
