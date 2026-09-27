# 桌面分发核对

更新日期：2026-09-27

## 当前发布状态

2026-09-27 源码候选 `edf0e51f` 的 Windows CI 五个 job 已通过。下文保留此前各阶段的事实和失败记录；其中“尚未生成 EXE”“Redis 方案未定”“停止在 EXE 前”等文字只描述当时阶段。DOCX 修复版与后续安全更新版 LocalTest 均已完成本机验收，未改变分发审查标记，也不能作为正式安装器上传。

安全更新版位于本地 `desktop/dist/local-test-security`：载荷 AnyIO 4.14.2、搜索运行时 pip 26.2.1；安装退出码 0、耗时 453.634 秒，44,416 个载荷文件及宿主文件哈希匹配。空数据首次启动 42.378 秒、重启 37.417 秒，注册登录、界面记忆、判题、35 条搜索结果、语音样例和后台任务通过；账户、密钥、窗口会话、记忆、Redis 数据重启后保留，两次服务清理通过。卸载退出码 0，1,665 个用户数据文件哈希不变，合成 profile 已归档而非删除。安装器 1,388,932,541 字节，SHA-256 `53b4b7d989721535099fa865e53c9615d34243a85dd973dfeae06964c73123ff`，Authenticode 为 `NotSigned`，`redistributionReviewed=false`。验收来自现有开发机，`cleanWindows=false`；原始证据在被忽略的 `.planning/desktop-feasibility`。

人工语音、干净 Windows 和可信签名按用户本轮回复保留未验收。签名不是创建 GitHub 草稿或预发布的统一硬性要求。当前清单见 [Release Checklist](RELEASE_CHECKLIST.md)，草稿说明见 [发布说明](RELEASE_NOTES_0.1.0.md)。

## DOCX 修复版续验与分发材料

当前修复候选独立位于 `desktop/dist/local-test-docxfix`，此前 `local-test` 的已验收安装器和证据保留。修复保留 Docling 从 Word 样式识别出的无编号标题，避免套用 PDF 视觉标题过滤规则后把正文归入默认排除的前言；PDF 处理规则不变。回归测试先复现失败，修复后资料解析与资料 API 共 31 项通过，Ruff 通过。

真实 Word 样例解析得到 4 个目录节点、3 个正文切片，确认目录及真实模型建课通过。课程对话与 PDF/DOCX 队列导出已通过。练习验收驱动原先遗漏个人模型的结构化能力测试，已补入真实设置测试接口；聊天与生成配置均通过能力测试。安装与运行验收必须串行：安装器会关闭同名应用，安装期间被中断的测试不计通过。修复版实际安装退出码 0，耗时 711.017 秒，44,381 个载荷文件和宿主文件摘要通过。实际安装版的真实模型练习与反馈、课程对话、PDF/DOCX 队列导出全部通过，临时配置剩余 0。归档学习测试数据后，从空目录首次启动 36.215 秒，重启 33.021 秒，基础功能、长期记忆、后台任务及持久化通过，关闭后全部受控服务停止。卸载前后 1,665 个数据文件哈希不变。安装器 1,388,952,974 字节，SHA-256 `f3b9d1da0dbb0730f3e6e6085d8d5a95a28be031621b611a8ebb657a50e2da8c`；签名状态 NotSigned。完整结果和使用说明位于候选旁，首次学习建课证据与后续安装版续验证据分别保留。

分发材料已与修复候选重新对齐：200 个 Python 包、439 处载荷通知引用、8 份顶层许可补充、7 份 Cygwin 对应源码归档摘要通过；另外收集 33 份公开来源文件和源码材料。四组模型的 26 个上游文件与固定提交 Git/LFS 摘要相符，2 个本地来源记录单独标记。准确版本的模型卡显示：BGE 为 MIT，Docling layout 为 Apache-2.0，Docling tables 为 CDLA-Permissive-2.0；SenseVoice 转换仓库未声明许可，所链接父模型卡的 Apache-2.0 声明不代替历史转换链核对。

Sherpa 1.13.8 构建配方固定的 eSpeak NG 与 piper-phonemize 源码归档已下载并核对摘要，原生文件中存在相应功能标记。顶层 Sherpa 许可不能单独代表全部捆绑组件；wheel 的实际构建参数、源码与二进制对应关系及分发责任仍待核对。上述来源、固定提交和摘要见候选旁 `release-review/model-origin-review.json`、`model-notices/origin-chain.json`、`native-sherpa/source-archives.json`。`redistributionReviewed` 继续为 false；干净 Windows、可信签名与真实麦克风/中文朗读/人工界面验收仍未通过。

## 2026-09-27 安装包构建与验收进展

最终本机试装安装器已生成并通过实际安装验收：`desktop/dist/local-test/EduNova-LocalTest-Setup-0.1.0-x64.exe`，1,388,952,964 字节，SHA-256 为 `ae7c5fd0c94a41bead8c5e713c3d11f8fcfec8cb3b4296b14f06390cca7d3513`。同目录提供 `使用说明.md`、`SHA256SUMS.txt`、`验收摘要.json` 和另行收集的许可证补充材料。签名检查为 NotSigned，第三方分发核对仍为 false；不作为正式发布包。

最终安装退出码为 0，耗时 382.116 秒，当前用户卸载入口、桌面和开始菜单快捷方式正常。安装目录 44,381 个资源文件逐项哈希通过，安装后的 `EduNova.exe` 与 `resources/app.asar` 也与本次构建一致。以空数据目录启动实际安装后的 EXE：首次启动 42.215 秒，重启 35.056 秒；注册/登录、界面保存长期记忆、沙箱判题、35 条联网搜索结果、真实语音样例识别及后台子进程任务通过。重启后账户、密钥、窗口会话、长期记忆和 Redis 标记保留，两次关闭均确认全部受控服务停止。`installed-exe-results.json` 中 `packaged=true`、`firstRunDataAbsent=true`、`passed=true`。

最终自带卸载器完成卸载，1,665 个用户数据文件全部保留且哈希不变，程序与卸载注册表入口已移除，无安装目录所属残留进程。为让下次安装从空白账号开始，验收数据随后移至 `%APPDATA%/EduNova-acceptance-20260927-final`，没有删除。重启后的实际记忆界面截图已检查；不代替人工使用验收。原始证据保存在被忽略的 `.planning/desktop-feasibility`，精简验收摘要随包提供。本轮未提交、推送或公开发布。

应用运行时 PATH 仅保留 Windows System32，但验收仍在现有开发机上使用仓库自动化工具执行；`cleanWindows=false`，不把这一结果表述为干净 Windows 通过。真实麦克风、系统中文声音、人工保存对话框、全部导出流程和真实模型提供器调用不在本次安装包验收覆盖范围内。

保留原候选目录，以现有组装脚本创建 `installer-20260927/resources/edunova`，44,380 个文件、2,694,171,346 字节。预检发现 OpenAI SDK 的 `resources/uploads`、`types/uploads` 被通用目录规则误判，现仅对这两个精确 SDK 路径放行；用户上传目录、未登记文件及哈希不符仍阻断。新增回归后 12 项桌面测试通过，安装器构建成功。

第一版安装后发现 8 个文件缺失，构建解包目录中同一批文件全部存在：4 个 ARM 辅助二进制与 4 个深路径许可证。第一版已归档在 `desktop/dist/failed-20260927-first-install`，自带卸载器退出码为 0，应用主程序已移除，首次启动前没有创建用户数据目录。不得分发这一失败构建。

修复沿用现有构建器支持的 `ELECTRON_BUILDER_7Z_FILTER=BCJ`，没有修改第三方依赖或升级版本。官方同类问题与修复说明：https://github.com/electron-userland/electron-builder/pull/9988 。另将 8 个超过 160 字符的 Python 许可证相对路径迁至 `notices/python`，保留字节、原路径及哈希索引；最长文件相对路径降至 158 字符。新增许可证保留/幂等回归通过，Ruff 通过。第二版候选共 44,381 个文件、2,694,174,512 字节；清单 SHA-256 为 `06f75b98ac629014492e06b81fc7275b8a19a5daa553ed04541acc86f405802e`。

第二版安装退出码为 0，耗时 459.841 秒；安装目录 44,381 个文件全部通过哈希检查。实际首次启动发现 Windows AppData 重定向导致宿主字符串路径比较失败：Python 返回物理路径，Electron 使用逻辑路径，两者指向同一目录。现改为比较实际目录，保留拒绝不同 profile 的约束；目录联接回归及全部 13 项桌面测试通过。第二版安装器已归档至 `desktop/dist/failed-20260927-profile-path`，其 SHA-256 为 `9cc345b5a1675bf7c4afdec401676736321296a5c2dd9b48e13bf6e44f03f030`，不得与最终构建混用。

修复后的打包目录通过注册/登录、界面保存记忆、判题、47 条联网搜索结果、真实语音样例和后台子进程任务；重启后账户、密钥、会话、记忆和 Redis 标记保留，两次关闭全部受控服务停止。验收脚本已修正重启后需切换到 L3 长期学习信息视图，以及重复运行需先退出上次测试会话的步骤。实际卸载第二版程序后，1,668 个测试数据文件全部保留且哈希不变；这批数据已另行归档。最终构建的实际安装验收结果见本节开头，干净 Windows 验收尚未通过。

实际候选的两个 Python 环境共 200 个包，发现 442 个许可证/通知文件；缺失的 8 个包顶层许可已按对应官方版本补取，记录在本地 `notice-supplements/inventory.json`。这不代表原生二进制捆绑依赖、模型许可链及对应源码已全部核对完成。当前系统未发现 Windows Sandbox 可执行文件，不安装系统功能或更改系统策略来替代干净机器验收。

以下为此前阶段性记录；其中“尚未生成 EXE”的描述只适用于对应历史阶段，当前状态以本节为准。

## 当前执行边界更新

### 最新本机集成结果

当前 Electron 宿主与独立候选目录中的全部服务已完成一次首次启动和一次重启验收。首次启动耗时 33.769 秒；注册/登录、本地真实语音样例、联网搜索（34 条结果）、桌面沙箱代码判题和后台子进程任务通过；重启后账户、JWT、加密密钥和 Redis 标记保留，两次关闭均确认全部受控服务停止。报告位于本地 `prepared-installation-results.json`，`passed=true`，但 `packaged=false`、`cleanWindows=false`。自动化仍使用仓库测试工具，未使用真实模型提供器密钥。

集成中发现 SearXNG 源码归档启动时依赖 Git 查询版本。已通过其原生 `version_frozen.py` 机制记录固定上游提交，并纳入候选资源组装；安装后无需为搜索另装 Git。独立桌面代码判题验收 12 项通过，桌面单元测试 11 项通过。

为先进行本机安装验收，构建入口增加显式 `--local-test`：产物独立放在 `desktop/dist/local-test`，文件名带 `LocalTest`，不修改 `redistributionReviewed`，仍执行全部资源白名单和哈希检查。默认分发构建继续要求第三方材料核对通过，输出位于 `desktop/dist/release`。本机试装通过不等于可对外分发。

此次准备清理候选资源中的两个 Python 字节码缓存目录、刷新资源清单并生成本地试装包的命令被客户端执行策略拒绝，未给出具体规则，未重试。只读复查确认缓存仍在，且未生成安装器。候选清单需在后续获准构建前刷新。仍待完成：安装器生成及安装/卸载验收、干净 Windows 验收、随包第三方材料核对。

用户已明确授权继续制作 EXE/安装器，之前“在 EXE 前停止”的约束已经解除。以下各节保留阶段性证据，其旧停止条件不代表当前授权。视频和参赛 PDF 不在本轮工作范围；跨版本升级和自动更新不作为首个比赛安装包的新增目标。

已接入 electron-builder 26.15.3（MIT）和 NSIS 当前用户安装入口。选择它复用现有 Electron 宿主；比较的 Electron Forge Squirrel 方案会产生 Setup.exe、nupkg、RELEASES 并增加对应启动处理，因此本轮不迁移宿主框架。安装依赖的 npm audit 报告 0 个已知漏洞，仅覆盖该 npm 依赖范围。构建前要求逐文件哈希清单、运行资源白名单及分发材料核对；卸载默认保留用户数据。

Redis 8.10.2 Windows 构建附带的 8 个 DLL 已匹配 7 个 Cygwin 包：Cygwin 3.6.10-1、GCC/libstdc++ 14.4.0-1、libiconv 1.19-2、gettext 0.22.5-1、OpenSSL 3.5.8-1、zlib 1.3.2-1。部分原始哈希差异来自 Cygwin DLL 重定位，已使用官方 rebase 4.6.6-1 在审计副本上复现后确认字节一致。对应源码及 Redis/Windows 包装层标签源码已收齐，共 173,778,255 字节；来源、哈希、包索引与构建工作流保存在本地审计目录。源码收齐不等于全部通知整理完成，也没有宣称完整 Redis 二进制可重复构建；分发核对状态仍为未完成。

正式 `scripts/desktop_worker.py` 已通过 12 项隔离验收，包含实际 BGE 向量、超时终止、停止、进程崩溃、依赖与回调检查，试验 Redis 已停止且无记录中的残留子进程。当前应用生产者未使用 RQ scheduler、Retry 或回调；不将整个 RQ 框架的未用功能都扩大为此次安装包目标。延迟重试的测试只覆盖显式转移到期任务，不宣称 scheduler daemon 已验收。

首次启动准备程序已加入数据库初始化/迁移、Redis、语音、API 和 worker 服务清单，稳定保存数据库凭据和模型配置加密密钥，空闲时保留原端口，冲突时选择新端口；已有数据库缺少凭据时拒绝覆盖。6 项准备程序回归、10 项桌面测试及相关 Ruff 检查通过。完整资源组装、实际启动及剩余搜索/代码执行接入继续进行；尚无可交付 EXE 或干净 Windows 验收结论。

本文件记录当前开发环境对桌面分发所需运行时、模型、许可和系统依赖的核对结果。**初次审计未复制运行时或模型；后续已建立本地 staging 副本，始终没有生成 EduNova EXE 或安装器。** 当前结论是“核对完成，仍不可直接交付”。

## 已核实

- 4 组本地模型共 28 个文件，当前目录总计 862,948,937 bytes，约 823 MiB。
- BGE 和 SenseVoice 实际权重均与代码中已有固定 SHA-256 一致；4 组模型文件与 Hugging Face 缓存的 revision/etag 均一致。本地缓存一致性不等于远端签名验证。
- 当前开发目录中测得的组件合计 2,030,849,770 bytes，模型合计 862,948,937 bytes，合计约 2.70 GiB。这是开发目录测量值，不是最终安装包大小；其中包含重复依赖、开发文件和未裁剪运行时。
- backend `.venv` 的 `pyvenv.cfg` 指向 `C:\Program Files\Python312`；文档 AI 环境还通过 `.pth` 借用了主 `.venv` 的 site-packages。Python 官方说明 venv 不可直接移动或复制成独立交付环境。
- Node 当前来自 `E:/nodejs/node.exe`。Electron 的 Chromium/Node 通知文件必须随最终分发材料保留，不能按普通应用文件删除。
- 三个 Python 环境本机 `pip check` 均通过，但这只说明当前安装状态无已报告的依赖冲突，不能证明干净 Windows 可运行。

清单与哈希快照见 [model-assets.lock.json](../desktop/model-assets.lock.json)。原始开发目录的审计报告和生成脚本位于被忽略的 `.planning/desktop-feasibility/runtime-assets-inventory.json` 与 `audit_runtime_assets.py`；它们用于复核，不是最终 SBOM 或打包器。

## 模型与许可范围

| 模型 | 固定 revision | 当前声明/核对范围 |
| --- | --- | --- |
| BGE small zh v1.5 | `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59` | 固定模型卡声明 MIT；完整随包 notice 尚未整理 |
| SenseVoice Yue int8 | `355f4d4884d8afd08aef04b9007a8556d7b463b2` | 实际是 ASLP-lab/WSYue-ASR 粤语微调/转换分支；模型卡声明 Apache-2.0，转换与微调许可链仍待核对 |
| Docling Heron | `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` | 固定模型卡声明 Apache-2.0；模型 notice 尚未作为最终材料整理 |
| Docling tables | `fc0f2d45e2218ea24bce5045f58a389aed16dc23` | 固定模型卡声明 CDLA-Permissive-2.0；与 Docling 代码许可分开处理 |

本地 `MODEL_LICENSE`、模型卡和上游仓库标签不能自动证明整条转换/微调链已经获得再分发许可。Sherpa-ONNX 预编译包还需逐项核对其捆绑 GPL 组件及对应源码义务。

## 独立运行时预检

`validate_desktop_staging.py` 是进入打包前的阻断检查。它要求 Python、Node 和 Electron 都位于同一个候选 staging 根目录，并检查 `pyvenv.cfg` 和 `.pth` 是否仍引用外部开发机路径。它只读检查，不复制文件、不生成 EXE：

```powershell
.venv/Scripts/python.exe -X utf8 scripts/validate_desktop_staging.py `
  --root C:/EduNova/staging `
  --python C:/EduNova/staging/runtime/python/python.exe `
  --node C:/EduNova/staging/runtime/node/node.exe `
  --electron C:/EduNova/staging/runtime/electron/electron.exe `
  --json .planning/desktop-feasibility/staging-preflight.json
```

原开发目录会因外部 Python/Node 路径而失败。staging 的路径预检通过仅表示所检查的路径满足条件，不代表完整运行、发布许可或干净 Windows 验收通过。

## 当前分发缺口

1. **独立运行时已有组件试验，最终发布构建未完成。** 嵌入式 Python 候选已通过中文路径下的组件检查；仍需形成可复现依赖构建和完整服务闭环，并在没有本机 Python、Node、Docker 的干净 Windows 上启动验证。
2. **Redis 方案未定。** 当前 Redis Windows/Cygwin 目录缺少完整的可交付许可和源码材料；Redis 社区构建、Garnet、Memurai 的兼容性或再分发条款都不能直接推定。RQ 适配仍有断线恢复、启动重整、回调硬上限和 scheduler daemon 等待完成。
3. **模型和二进制通知材料不完整。** BGE、Docling 模型卡对应的完整 notice 尚未收齐；SenseVoice 转换/微调链仍需获得可审计的许可结论；Sherpa wheel 的捆绑组件需要最终清单。`docs/DEPENDENCY_LICENSES.md` 是开发依赖索引，不是最终随包 SBOM。
4. **系统依赖仍需实机验收。** PDF 导出会查找 Linux Noto 或 `C:\Windows\Fonts\msyh.ttc`/`simhei.ttf`；Windows 字体不能未经许可复制进安装包。中文朗读依赖用户系统已安装的中文声音。干净 Windows 的字体、中文声音和真实麦克风仍未验收。
5. **功能验收仍有边界。** 真实麦克风、人工保存对话框、所有导出生成器、完整语音/外部媒体流程和真实模型缓存性能仍未完成；代码执行的 OS 隔离也仍未完成。

## 下一步顺序

1. 做独立 Python/Node runtime staging 和最小启动闭环，保留项目业务状态、权限、导出和学习数据逻辑。
2. 对 Redis/RQ 做再分发决策并记录许可证、源码和维护路径；若不能满足交付条件，保留外置服务模式。
3. 收齐模型、Sherpa wheel、Electron/Chromium/Node、PostgreSQL 及搜索组件的最终 notice 和来源清单，生成带哈希的随包 manifest。
4. 在无开发运行时的干净 Windows 上验证启动、升级、备份恢复、字体、中文声音、麦克风和保存对话框。
5. 上述证据完成后，才进入 EXE/安装器生成和发布验收。

本文件是项目内的窄范围审计记录，不引入新的通用框架，也不替代正式的法律审查、完整 SBOM 或发布验收。

## 依据

- [Python venv 文档](https://docs.python.org/3.12/library/venv.html)
- [第三方通知索引](../THIRD_PARTY_NOTICES.md)
- [依赖许可证索引](DEPENDENCY_LICENSES.md)
- [本地语音说明](LOCAL_SPEECH.md)
- [桌面运行时合同](DESKTOP_RUNTIME.md)

## 独立运行时实际试验更新

本地 staging 已加入官方 Python 3.12.10 嵌入包、Node/Electron 副本、应用源码和四组模型。清除了 staging 中 38 个下载缓存文件，锁定的 28 个模型文件 SHA-256 全部匹配。

完整依赖联网安装因 PyPI/PyTorch 连接超时失败。随后复用既有已验证环境，通过包元数据解析 166 个运行依赖，并按 wheel RECORD 校验复制 36,090 个文件到新嵌入式 Python；未复制虚拟环境配置或借用项目 `.pth`。这是本地可迁移性试验，不是最终可复现的发布构建，原有分批安装候选仍保留，未作为通过证据。

子进程 PATH 仅保留 Windows System32，使用独立工作目录及合成配置；运行依赖无重复版本、无已报告的元数据冲突，所有 Python 搜索路径位于 staging。真实 BGE 输出 512 维向量，SenseVoice 样例转写非空，Docling 保留课程 DOCX/PPTX 内容，实际 API 的健康接口和 116 个 OpenAPI 路径可读，测试 API 已停止。API 验证不含数据库/Redis 闭环。

首次试验发现中文安装路径问题：Docling PDF 原生解析器在 `python-独立 验证` 路径下无法打开实际存在的 glyph 资源；移动相同运行时到 `python-complete` 后，两页课程 PDF 解析及内容核对通过。原始失败记录保留在 `acceptance/chinese-runtime-results.json`，不同路径累计结果保留在 `acceptance/prior-mixed-path-results.json`。

2026-09-26 已在应用适配层加入窄范围兼容：仅当 Windows 上 `docling_parse` 的安装目录含非 ASCII 字符时，选择 Docling 自带的 `PyPdfiumDocumentBackend`；其他路径继续使用默认后端。未新增依赖，布局/表格模型、离线设置、超时和页码合同保持不变；解析失败仍报错，不吞掉损坏文档或缺失依赖。

选择依据：安装的 docling-parse 7.8.0 从模块路径取得资源目录，并通过 C++ 窄字符路径打开 glyph 文件；上游输入 PDF 的 Unicode 修复不能直接当作资源读取修复。复用 [Docling 官方后端配置](https://docling-project.github.io/docling/v2/#setting-up-a-documentconverter)，没有修改第三方包或自研 PDF 解析器。资源路径处理见 [docling_resources.h](https://github.com/docling-project/docling-parse/blob/v7.8.0/src/pybind/docling_resources.h)。

同一中文运行时、同一两页课程 PDF 的对照试验中，默认后端复现失败，PDFium 后端保留全部核对正文与页码，证据为 `acceptance/unicode-pdf-comparison.json`。随后同步应用源码，在同一次中文路径运行中完成依赖、向量、语音、DOCX、PPTX、PDF、API 共 7 项组件检查，全部通过；19 项相关 pytest 回归与 Ruff 通过。最新 `acceptance/runtime-results.json` 只记录本次调用，不再把其他路径的旧通过项混入当前结果。此证据不覆盖复杂教材的全部排版质量，也不表示完整客户端或干净 Windows 已验收。

## 独立运行时接回桌面窗口的试验

2026-09-26 使用 staging 内的中文路径嵌入式 Python、Node、Electron、应用后端、PostgreSQL、Redis 和模型，复用原有桌面闭环验收。子服务 PATH 仅保留 Windows System32，未使用开发虚拟环境。通过数据库初始化与迁移、RQ 子任务输出三组 512 维向量、真实 Electron 学习闭环、记忆 JSON 导出与 API 内容一致性，以及关闭后重新打开的数据保留检查。重启后练习记录、三条答案、掌握度 100 和 Redis 合成标记均保留。

两次窗口生命周期结束后，所有试验服务已停止；PostgreSQL、Redis、RQ worker 优雅退出，API/前端由控制器清理。试验凭据仅用于新建的私有测试目录，临时运行清单和初始化密码文件已经移除。证据：`runtime-staging/acceptance/staged-stack-results.json`，测试目录 `acceptance/独立运行时窗口-092bb109`。

这个结果仍有明确边界：前端 Vite preview、Playwright 驱动和浏览器用例来自仓库；学习模型为既有合成提供器；录音为模拟设备，保存对话框由测试自动选择；Redis 分发和 Windows RQ 适配仍是试验方案。该闭环证明独立 Python 可以接回现有应用，不是最终自包含客户端或干净 Windows 交付证明。

上述借用仓库预览服务的问题已在下一节试验中解决。仍需完成 Redis/RQ 分发及可靠性、运行时/模型通知材料、完整功能与代码执行隔离、可复现依赖构建、升级备份和干净 Windows 验收。继续保持生成 EduNova EXE/安装器前停止的边界。

## 前端独立托管试验完成

2026-09-26 新增桌面专用 `backend.app.desktop_app:create_app` 入口，复用安装版本已有的 FastAPI 前端托管能力。前端页面、构建资源与原有 API 共用同一个回环端口；移除 Vite preview 服务、前端代理配置和第二个监听端口。普通 API/容器入口不变，未新增依赖。实现选择和运行条目示例见 `DESKTOP_RUNTIME.md` 与 `desktop/README.md`。

复制既有 `frontend/dist` 中 143 个公开构建文件（19,302,196 字节）到 staging 的 `app/frontend`，逐文件比对 SHA-256，清单位于 `runtime-staging/acceptance/frontend-assets.json`。没有将前端源码、`.env` 或 `node_modules` 作为应用运行资源复制进去；这次复用已有构建产物，并未重新构建前端。

验证结果：

- 14 项相关 pytest 检查通过，覆盖静态托管、浏览器深层路由、HTTP 文件语义、API 错误与流式内容、缺失构建和路径越界；Ruff 通过。
- 实际 Electron 窗口使用 staging 中的前后端资源，在没有 Vite 进程的情况下通过页面刷新、学习闭环、RQ 向量、媒体权限与记忆导出测试。
- 真实服务器提供登录/深层路由 HTML；缺失 API/静态资源保持 404；实际 Pyodide WASM 文件的 MIME 和范围读取通过。
- 关闭后重新打开，学习记录、掌握度和 Redis 标记保留；两次生命周期后全部受控服务停止，临时 manifest 与初始化密码文件移除。

证据为 `runtime-staging/acceptance/self-contained-stack-results.json`，`passed=true`、`borrowed_frontend_preview=false`，试验目录为 `acceptance/独立前端窗口-4de61afd`。应用运行服务与前端资源位于 staging；自动化测试本身仍使用仓库中的 Playwright 和用例，合成学习提供器/模拟麦克风的边界不变。这证明本机试验目录已能独立托管前端，不证明无开发环境的干净 Windows、所有 AI 服务或最终分发材料已验收。

接下来优先收口已列出的 Redis/RQ 分发与可靠性问题；可复现构建、许可通知、安全隔离、其余功能/硬件、升级备份和干净 Windows 门槛继续保留。没有生成 EduNova EXE/安装器，没有提交或推送。
