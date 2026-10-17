# 免Key联网搜索

SearXNG 默认作为独立容器运行，经 WebSearchService/httpx 接入；Trafilatura 提取正文，HTTPCore 限制网络连接，无需额外 API Key。适配不替换 LangGraph，结果仅作为带 URL 的外部补充，不是教材或评分证据。

## 启动

搜索随主编排启动，无需单独部署。首次安装、升级与停止统一按[部署指南](DEPLOYMENT.md)操作。服务运行后可检查搜索连接：

```powershell
docker compose exec -T backend python -m backend.integration.keyless_search_check
```

初始化生成随机 SearXNG 内部签名密钥，无需购买 Key。容器只供后端经 Docker 网络访问，不映射宿主端口。迁移清理 `.env` 中旧搜索提供方、端点和 Key，保留其他设置；失败不转用模型原生联网或付费接口。

## 使用边界

聚合服务仍将查询词发送给上游引擎，请勿输入私密资料。可用性取决于网络、限流、超时和验证码，可能部分或全部失败。须启用 JSON 接口，返回 403 时不绕过限制。

适配层保留引擎不可用提示，过滤非 HTTP(S)、缺失 URL 与重复来源。

## 视频和网页正文

视频先搜索 `videos` 类别，经 B站/YouTube 链接与主题校验后优先 B站；无合格结果再作受限站点查询。链接不证明观看、读取字幕或播放成功，`embed_status` 保持 `unknown`，不绕过登录、版权或验证码限制。

答疑最多读取前 2 条来源，每页最多 1 MB，摘录不超过 1800 字符。保留原 URL、摘要与引用身份，正文另存 `content`，标记 `read_status=read`；未读则仅保留摘要并提示全文未核实。读取状态不证明真实性或回答正确，外部摘录不参与评分或掌握度。

仅允许 HTTP(S) 标准端口，不带凭证、Cookie 或环境代理。检查全部 DNS 结果，固定已校验公网 IP，TLS 验证原域名；最多 3 次请求，每跳重新检查。禁止私网、环回、云元数据和保留地址，不执行 JavaScript、加载子资源或解压响应。单次网络操作最多 2 秒，读取循环预算 6 秒；系统 DNS 与正文提取不能硬实时取消，因此不承诺严格 6 秒 SLA。失败不切换付费接口。

使用 `198.18.0.0/15` Fake-IP DNS 时，正文读取安全失败、保留摘要。部署方需提供真实公网解析，如 `redir-host`，不能放开保留地址检查。动态页面、403/429、验证码和无正文页也可能失败。

正文提取使用 Trafilatura 2.2.0（Apache-2.0），受限网络连接使用 HTTPCore 1.0.9（BSD-3-Clause），无需模型权重、GPU或付费服务。

依据：[Trafilatura](https://trafilatura.readthedocs.io/en/latest/faq.html)、[Haystack HTMLToDocument](https://docs.haystack.deepset.ai/docs/htmltodocument)、[HTTPCore公开网络适配接口](https://www.encode.io/httpcore/network-backends/)。

可手动运行真实公开来源检查（会联网，不调用主模型或写数据库）：

```powershell
docker compose exec -T backend python -m backend.integration.web_sources_check --require-body
```

严格模式要求两项教学视频查询及 Python 官方中文正文均成功。去掉 `--require-body` 只验证视频检索，仍打印正文状态；播放与回答质量另验。

真实播放可选：PowerShell 设置 `$env:EDUNOVA_LIVE_VIDEO='1'` 后运行 `./scripts/test_e2e.ps1`。测试临时替换隔离数据库资源页的合成视频，要求 B站播放超过 2 秒并保留原链接，不写正式课程。默认 E2E 不依赖外部视频平台；结束后用 `Remove-Item Env:EDUNOVA_LIVE_VIDEO` 清除开关。

搜索默认语言为 `zh-CN`，也可查询英文内容。视频是否可播放取决于平台、地区、网络和浏览器限制。

镜像按 Compose 的 SHA256 固定，升级须重做质量、安全与回归检查。SearXNG 是 AGPL-3.0-or-later 独立服务，项目未复制其实现；再分发镜像或修改服务须保留许可与源码获取信息。

官方文档：[Search API](https://docs.searxng.org/dev/search_api)、[容器安装](https://docs.searxng.org/admin/installation-docker)、[源码和许可](https://github.com/searxng/searxng)。
