# 免Key联网搜索

SearXNG默认随项目作为独立容器运行，通过现有WebSearchService/httpx接入，不替换LangGraph。正文读取采用本地Trafilatura提取及HTTPCore受限连接，不需要额外API Key。搜索结果仍是带URL的外部补充引用，不是课程教材或评分证据。

## 启动

Windows运行 `02_Start_EduNova.bat`，自动初始化并启动搜索；`06` 是兼容别名，不再启动第二套配置。也可在已准备.env和本地向量模型后执行：

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

## 边界与试验

本地运行的是聚合服务，实际仍联网访问上游搜索引擎，查询词会发送给这些引擎。不要将私密资料作为联网问题输入。不是离线搜索，不保证每个网络环境均可访问；引擎限流、超时或验证码可造成部分或全部失败。JSON接口需启用，接口返回403时不会绕过限制。

2026-09-24固定版本试验：公开中文学习问题“Python 官方文档 列表 推导式”返回29条来源，首条Python官方文档；Brave限流。容器当时内存约112 MiB，镜像约382MB，不是峰值或完整质量评测。适配层保留部分引擎不可用提示，过滤非HTTP(S)/缺失URL和重复来源。

## 视频和网页正文

视频资源先搜索SearXNG的 `videos` 类别，通过既有B站/YouTube链接和主题门禁后优先B站；无合格结果再执行原有受限站点查询。视频链接不代表已观看、字幕已读取或播放成功，`embed_status` 仍为 `unknown`。不绕过站点登录、版权或验证码限制。

答疑搜索成功后最多读取前2条来源，每页最多1MB，输出不超过1800字符的正文摘录。原URL、搜索摘要和引用身份保留；已读正文独立存为 `content`，`read_status=read`。其他状态只保留摘要并提示未核实全文；该状态不代表内容真实性或模型回答已验证。课程评分和掌握度不使用这些外部摘录。

只允许HTTP(S)标准端口，无登录凭证、Cookie、环境代理；连接时检查全部DNS结果并固定已校验的公网IP，TLS仍验证原域名。最多3次请求，每跳重新检查；不执行JavaScript、不加载子资源、不解压压缩响应，不读取私网、环回、云元数据、保留地址。单次网络操作最多2秒、读取循环预算6秒；操作系统DNS解析和正文提取不是硬实时可取消操作，因此不是严格6秒SLA。失败不会切换付费接口。

如果本机代理使用 `198.18.0.0/15` Fake-IP DNS，正文读取会安全失败并保留摘要。需由部署方为后端使用真实公网解析（例如将代理DNS模式设为 `redir-host`）；不要为此放开保留地址检查。2026-09-24开发机经用户授权调整当前代理DNS后，后端及AI worker安全读取Python官方文档各1800字符，严格来源检查通过。此结果只覆盖当时网络和样例，动态页面、403/429、验证码和无正文页仍可能读取失败。

正文工具比较了Trafilatura、readability-lxml以及已有lxml/bs4。选择Trafilatura以避免自写正文规则；Haystack HTMLToDocument也使用该提取器，LangChain WebBaseLoader主要提供bs4全文封装，因此未引入额外框架。固定Trafilatura 2.2.0（Apache-2.0）、HTTPCore 1.0.9（BSD-3-Clause，原已间接安装）；新增提取器及其轻量依赖，无模型权重、GPU或付费服务。OSV在选型时对这两个版本及readability-lxml 0.9均未返回已知公告，不代表完整安全认证。

依据：[Trafilatura](https://trafilatura.readthedocs.io/en/latest/faq.html)、[Haystack HTMLToDocument](https://docs.haystack.deepset.ai/docs/htmltodocument)、[HTTPCore公开网络适配接口](https://www.encode.io/httpcore/network-backends/)。

可手动运行真实公开来源检查（会联网，不调用主模型或写数据库）：

```powershell
docker compose exec -T backend python -m backend.integration.web_sources_check --require-body
```

严格模式要求两个教学视频查询及Python官方中文正文均成功，否则非零退出。去掉 `--require-body` 只把视频检索作为通过条件，正文状态仍打印；不得把该模式成功解释为正文读取已验收。浏览器实际播放和模型回答质量需另行验证。

可选真实播放验收：在PowerShell设置 `$env:EDUNOVA_LIVE_VIDEO='1'` 后运行 `./scripts/test_e2e.ps1`。它在隔离数据库的真实资源页临时替换合成视频载荷，要求B站视频播放时间推进超过2秒并保留原平台链接；不写入正式课程。默认E2E不依赖外部视频平台，测试结束可用 `Remove-Item Env:EDUNOVA_LIVE_VIDEO` 清除开关。

2026-09-24该可选验收通过，样例为B站 `BV1b54y117KG`。这证明当时网络和浏览器下的页内播放，不保证其他视频、地区或平台均可播放。

实际后端POST试验曾在未指定语言时返回空结果，明确中文语言后相同问题返回20条；配置因此明确 `default_lang: zh-CN`。英文问题也实测返回来源。Brave、DuckDuckGo和Wikidata先后出现限流/验证码，不能将少量成功查询表述为长期稳定或全面覆盖。

固定镜像使用Compose中的SHA256摘要，升级需重新做质量/安全与回归检查。SearXNG是AGPL-3.0-or-later独立服务，源码与许可见官方仓库；本项目没有复制其实现。重新分发镜像或修改服务时需保留相应许可和源码获取信息。

同日使用现有Trivy 0.69.3及更新后的漏洞库扫描固定镜像，识别到的Python依赖HIGH/CRITICAL记录为0；报告没有提供完整OS组件扫描覆盖，不能视为完整供应链认证。GitHub公开安全公告页当日无已发布公告，也不代表不存在漏洞。扫描报告保存在本地忽略目录，未上传。

## 选择依据

比较了现有Tavily、嵌入式DDGS和独立SearXNG：Tavily需要Key；DDGS可以免Key但新增应用内依赖且同样依赖上游；SearXNG适合隔离部署，成熟聚合实现由上游维护。LangChain社区SearxSearchWrapper仍需要独立SearXNG实例，仅为HTTP包装，因此复用已有httpx更少依赖；Haystack的Serper组件仍需Key。没有自研搜索引擎或迁移Agent框架。

官方依据：[Search API](https://docs.searxng.org/dev/search_api)、[容器安装](https://docs.searxng.org/admin/installation-docker)、[源码和许可](https://github.com/searxng/searxng)、[DDGS](https://github.com/deedy5/ddgs)、[LangChain适配源码](https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/utilities/searx_search.py)、[Haystack组件](https://docs.haystack.deepset.ai/docs/websearch)。
