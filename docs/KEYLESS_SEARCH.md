# 免Key联网搜索

SearXNG作为独立可选容器运行，通过现有WebSearchService/httpx接入，不新增Python依赖、不替换LangGraph。搜索结果仍是带URL的外部补充引用，不是课程教材或评分证据。

## 启动

Windows运行 `06_Start_Keyless_Search.bat`；脚本先执行02初始化，再启动搜索覆盖配置。也可在已准备.env和本地向量模型后执行：

```powershell
./scripts/initialize_env.ps1
docker compose -f docker-compose.yml -f docker-compose.search.yml up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.search.yml exec -T backend python -m backend.integration.keyless_search_check
```

初始化只新增随机SearXNG内部密钥，不是购买的API Key。搜索容器不映射宿主机端口；仅供后端通过Docker网络访问。覆盖配置清空搜索API Key，并明确选择SearXNG；该模式跳过模型原生联网工具，失败不会转用Tavily或厂商付费搜索。02仍是基本学习启动，后续需要搜索请使用06入口。03停止入口也会停止同项目的搜索容器；手动停止搜索版使用：

```powershell
docker compose -f docker-compose.yml -f docker-compose.search.yml down
```

## 边界与试验

本地运行的是聚合服务，实际仍联网访问上游搜索引擎，查询词会发送给这些引擎。不要将私密资料作为联网问题输入。不是离线搜索，不保证每个网络环境均可访问；引擎限流、超时或验证码可造成部分或全部失败。JSON接口需启用，接口返回403时不会绕过限制。

2026-09-24固定版本试验：公开中文学习问题“Python 官方文档 列表 推导式”返回29条来源，首条Python官方文档；Brave限流。容器当时内存约112 MiB，镜像约382MB，不是峰值或完整质量评测。适配层保留部分引擎不可用提示，过滤非HTTP(S)/缺失URL和重复来源；不抓取返回的网页，URL不会成为服务端任意请求目标。

实际后端POST试验曾在未指定语言时返回空结果，明确中文语言后相同问题返回20条；配置因此明确 `default_lang: zh-CN`。英文问题也实测返回来源。Brave、DuckDuckGo和Wikidata先后出现限流/验证码，不能将少量成功查询表述为长期稳定或全面覆盖。

固定镜像使用Compose中的SHA256摘要，升级需重新做质量/安全与回归检查。SearXNG是AGPL-3.0-or-later独立服务，源码与许可见官方仓库；本项目没有复制其实现。重新分发镜像或修改服务时需保留相应许可和源码获取信息。

同日使用现有Trivy 0.69.3及更新后的漏洞库扫描固定镜像，识别到的Python依赖HIGH/CRITICAL记录为0；报告没有提供完整OS组件扫描覆盖，不能视为完整供应链认证。GitHub公开安全公告页当日无已发布公告，也不代表不存在漏洞。扫描报告保存在本地忽略目录，未上传。

## 选择依据

比较了现有Tavily、嵌入式DDGS和独立SearXNG：Tavily需要Key；DDGS可以免Key但新增应用内依赖且同样依赖上游；SearXNG适合隔离部署，成熟聚合实现由上游维护。LangChain社区SearxSearchWrapper仍需要独立SearXNG实例，仅为HTTP包装，因此复用已有httpx更少依赖；Haystack的Serper组件仍需Key。没有自研搜索引擎或迁移Agent框架。

官方依据：[Search API](https://docs.searxng.org/dev/search_api)、[容器安装](https://docs.searxng.org/admin/installation-docker)、[源码和许可](https://github.com/searxng/searxng)、[DDGS](https://github.com/deedy5/ddgs)、[LangChain适配源码](https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/utilities/searx_search.py)、[Haystack组件](https://docs.haystack.deepset.ai/docs/websearch)。
