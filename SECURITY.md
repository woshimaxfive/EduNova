# 安全策略

EduNova 处理学习资料、用户画像和模型凭据，因此安全问题请勿通过公开 Issue 披露。

## 报告漏洞

请使用 GitHub 仓库的 **Report a vulnerability** / Private Vulnerability Reporting 提交报告，并尽量包含：

- 受影响版本或提交；
- 最小复现步骤；
- 影响范围；
- 已采取的临时缓解措施。

报告中不要附带真实 API Key、账号密码、JWT、学生资料或其他个人信息。如凭据可能已经暴露，请先在对应 Provider 撤销或轮换凭据。

维护者在公开仓库前应确认 GitHub Private Vulnerability Reporting 已启用。若私密报告入口暂不可用，请等待维护者提供安全联系渠道，不要改用公开 Issue。

## 支持范围

安全修复以最新发布版本和 `main` 分支为主。更早版本可能需要先升级后才能获得修复。

完整的产品安全边界、日志脱敏、上传隔离和密钥处理约束见 [docs/SECURITY.md](docs/SECURITY.md)。
