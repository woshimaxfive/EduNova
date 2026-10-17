# Windows 桌面分发说明

## 安装与数据

目标平台为 Windows x64，从 [Releases](https://github.com/woshimaxfive/EduNova/releases/tag/v0.1.0-desktop-source-preview) 下载 EXE，安装后直接启动，无需 Docker。版本信息以发布页实际附件为准。

安装器面向当前用户，创建桌面与开始菜单快捷方式，首次运行初始化服务和数据。账号、学习记录与设置通常位于 `%APPDATA%/EduNova`，卸载默认保留。备份或迁移时保护数据库、资料和密钥，勿上传到问题反馈。

主模型服务需在应用中配置，网络请求和费用由所选服务决定。中文朗读依赖系统中文声音。

## 第三方材料

分发包须携带组件许可证、版权通知、模型来源和适用的对应源码材料，见[第三方声明](../THIRD_PARTY_NOTICES.md)和[依赖许可](DEPENDENCY_LICENSES.md)。模型许可按随包固定版本核对，不能从推理运行时许可证推断。

## 下载与验证

可用 SHA-256 核对下载完整性；校验文件不是必需附件，摘要以 GitHub 附件元数据或发布者提供的值为准。文件名、版本号和构建成功不能证明来源与完整性。签名、兼容性及已知限制见[发布说明](RELEASE_NOTES_0.1.0.md)。

## 源码构建

构建命令和运行配置见 [桌面 README](../desktop/README.md)，运行时接口见 [桌面运行时](DESKTOP_RUNTIME.md)，分发检查要求见 [发布清单](RELEASE_CHECKLIST.md)。
