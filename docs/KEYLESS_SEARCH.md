# 免Key联网搜索

SearXNG默认随项目作为独立容器运行，通过现有WebSearchService/httpx接入，不替换LangGraph。正文读取采用本地Trafilatura提取及HTTPCore受限连接，不需要额外API Key。搜索结果仍是带URL的外部补充引用，不是课程教材或评分证据。

## 启动

Windows运行 `02_Start_EduNova.bat`，自动初始化并启动搜索。也可在已准备.env及本地向量、语音模型后执行：

```powershell
./scripts/initialize_env.ps1
./scripts/migrate_local_search_env.ps1
docker compose up -d --build --wait
docker compose exec -T backend python -m backend.integration.keyless_search_check
```

初始化自动生成随机SearXNG内部签名密钥，不是购买的API Key。搜索容器不映射宿主机端口，仅供后端通过Docker网络访问。迁移脚本移除 `.env` 中旧搜索提供方、端点和Key，保留主模型、语音及其他设置；默认Compose强制使用本地搜索并清空旧Key，Tavily适配已移除。搜索失败不会转用模型原生联网或付费接口。`docker-compose.search.yml` 仅保留为空兼容覆盖文件。03停止入口会停止同项目全部服务；手动停止使用：

```powershell
docker compose down
```

## 使用边界

本地运行的是聚合服务，实际仍联网访问上游搜索引擎，查询词会发送给这些引擎。不要将私密资料作为联网问题输入。不是离线搜索，不保证每个网络环境均可访问；引擎限流、超时或验证码可造成部分或全部失败。JSON接口需启用，接口返回403时不会绕过限制。

适配层保留部分引擎不可用提示，过滤非HTTP(S)/缺失URL和重复来源。

## 视频和网页正文

视频资源先搜索SearXNG的 `videos` 类别，通过既有B站/YouTube链接和主题门禁后优先B站；无合格结果再执行原有受限站点查询。视频链接不代表已观看、字幕已读取或播放成功，`embed_status` 仍为 `unknown`。不绕过站点登录、版权或验证码限制。

答疑搜索成功后最多读取前2条来源，每页最多1MB，输出不超过1800字符的正文摘录。原URL、搜索摘要和引用身份保留；已读正文独立存为 `content`，`read_status=read`。其他状态只保留摘要并提示未核实全文；该状态不代表内容真实性或模型回答已验证。课程评分和掌握度不使用这些外部摘录。

只允许HTTP(S)标准端口，无登录凭证、Cookie、环境代理；连接时检查全部DNS结果并固定已校验的公网IP，TLS仍验证原域名。最多3次请求，每跳重新检查；不执行JavaScript、不加载子资源、不解压压缩响应，不读取私网、环回、云元数据、保留地址。单次网络操作最多2秒、读取循环预算6秒；操作系统DNS解析和正文提取不是硬实时可取消操作，因此不是严格6秒SLA。失败不会切换付费接口。

如果本机代理使用 `198.18.0.0/15` Fake-IP DNS，正文读取会安全失败并保留摘要。需由部署方为后端使用真实公网解析（例如将代理DNS模式设为 `redir-host`）；不要为此放开保留地址检查。动态页面、403/429、验证码和无正文页仍可能读取失败。

正文提取使用 Trafilatura 2.2.0（Apache-2.0），受限网络连接使用 HTTPCore 1.0.9（BSD-3-Clause），无需模型权重、GPU或付费服务。

依据：[Trafilatura](https://trafilatura.readthedocs.io/en/latest/faq.html)、[Haystack HTMLToDocument](https://docs.haystack.deepset.ai/docs/htmltodocument)、[HTTPCore公开网络适配接口](https://www.encode.io/httpcore/network-backends/)。

可手动运行真实公开来源检查（会联网，不调用主模型或写数据库）：

```powershell
docker compose exec -T backend python -m backend.integration.web_sources_check --require-body
```

严格模式要求两个教学视频查询及Python官方中文正文均成功，否则非零退出。去掉 `--require-body` 只把视频检索作为通过条件，正文状态仍打印；不得把该模式成功解释为正文读取已验收。浏览器实际播放和模型回答质量需另行验证。

可选真实播放验收：在PowerShell设置 `$env:EDUNOVA_LIVE_VIDEO='1'` 后运行 `./scripts/test_e2e.ps1`。它在隔离数据库的真实资源页临时替换合成视频载荷，要求B站视频播放时间推进超过2秒并保留原平台链接；不写入正式课程。默认E2E不依赖外部视频平台，测试结束可用 `Remove-Item Env:EDUNOVA_LIVE_VIDEO` 清除开关。

搜索默认语言为 `zh-CN`，也可查询英文内容。视频是否可播放取决于平台、地区、网络和浏览器限制。

固定镜像使用Compose中的SHA256摘要，升级需重新做质量/安全与回归检查。SearXNG是AGPL-3.0-or-later独立服务，源码与许可见官方仓库；本项目没有复制其实现。重新分发镜像或修改服务时需保留相应许可和源码获取信息。

官方文档：[Search API](https://docs.searxng.org/dev/search_api)、[容器安装](https://docs.searxng.org/admin/installation-docker)、[源码和许可](https://github.com/searxng/searxng)。
