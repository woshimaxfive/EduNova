# 直接依赖许可证清单

本文件由 `scripts/generate_dependency_licenses.py` 从固定依赖和本地包元数据生成；传递依赖由供应链门禁继续扫描。

| Python 依赖 | 版本 | 来源 | 声明许可证 | 用途 |
| --- | --- | --- | --- | --- |
| alembic | 1.18.5 | [alembic](https://github.com/sqlalchemy/alembic/) | MIT | 数据库迁移 |
| bcrypt | 5.0.0 | 需复核 | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| boto3 | 1.43.47 | [boto3](https://github.com/boto/boto3) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| cryptography | 49.0.0 | 需复核 | Apache-2.0 OR BSD-3-Clause | 项目直接运行、测试或构建依赖 |
| docling-slim | 2.113.0 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| fastapi | 0.138.2 | [fastapi](https://github.com/fastapi/fastapi) | MIT | 后端 API 与 OpenAPI |
| httpx | 0.28.1 | [httpx](https://github.com/encode/httpx) | BSD-3-Clause | 项目直接运行、测试或构建依赖 |
| json-repair | 0.61.4 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| langchain | 1.3.11 | [langchain](https://github.com/langchain-ai/langchain) | MIT | 项目直接运行、测试或构建依赖 |
| langgraph | 1.2.7 | [langgraph](https://github.com/langchain-ai/langgraph/tree/main/libs/langgraph) | MIT | 学习闭环状态图编排 |
| openai | 2.45.0 | [openai](https://github.com/openai/openai-python) | Apache-2.0 | OpenAI-compatible 模型协议适配 |
| opencv-python-headless | 未安装 | 需复核 | 需在构建镜像中复核 | 项目直接运行、测试或构建依赖 |
| opentelemetry-exporter-otlp-proto-http | 1.43.0 | [opentelemetry-exporter-otlp-proto-http](https://github.com/open-telemetry/opentelemetry-python) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| opentelemetry-instrumentation-fastapi | 0.64b0 | [opentelemetry-instrumentation-fastapi](https://github.com/open-telemetry/opentelemetry-python-contrib) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| opentelemetry-instrumentation-httpx | 0.64b0 | [opentelemetry-instrumentation-httpx](https://github.com/open-telemetry/opentelemetry-python-contrib) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| opentelemetry-instrumentation-redis | 0.64b0 | [opentelemetry-instrumentation-redis](https://github.com/open-telemetry/opentelemetry-python-contrib) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| opentelemetry-instrumentation-sqlalchemy | 0.64b0 | [opentelemetry-instrumentation-sqlalchemy](https://github.com/open-telemetry/opentelemetry-python-contrib) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| opentelemetry-sdk | 1.43.0 | [opentelemetry-sdk](https://github.com/open-telemetry/opentelemetry-python) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| pgvector | 0.4.2 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| pip-audit | 2.10.1 | [pip-audit](https://github.com/pypa/pip-audit) | 需复核 | 项目直接运行、测试或构建依赖 |
| psycopg | 3.3.4 | 需复核 | LGPL-3.0-only | 项目直接运行、测试或构建依赖 |
| puremagic | 2.2.0 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| pydantic-settings | 2.14.2 | [pydantic-settings](https://github.com/pydantic/pydantic-settings) | MIT | 项目直接运行、测试或构建依赖 |
| PyJWT | 2.13.0 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| pypdf | 6.14.2 | [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | 项目直接运行、测试或构建依赖 |
| pytest | 9.1.1 | [pytest](https://github.com/pytest-dev/pytest) | MIT | 项目直接运行、测试或构建依赖 |
| pytest-asyncio | 1.4.0 | 需复核 | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| python-docx | 1.2.0 | [python-docx](https://github.com/python-openxml/python-docx) | MIT | 项目直接运行、测试或构建依赖 |
| python-multipart | 0.0.32 | [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| python-pptx | 1.0.2 | [python-pptx](https://github.com/scanny/python-pptx) | MIT | 项目直接运行、测试或构建依赖 |
| ragas | 未安装 | 需复核 | 需在构建镜像中复核 | 项目直接运行、测试或构建依赖 |
| redis | 8.0.1 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| reportlab | 5.0.0 | [reportlab](https://www.reportlab.com/) | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. | 项目直接运行、测试或构建依赖 |
| rq | 2.10.0 | 需复核 | BSD-2-Clause | 项目直接运行、测试或构建依赖 |
| ruff | 0.15.20 | [ruff](https://github.com/astral-sh/ruff) | MIT | 项目直接运行、测试或构建依赖 |
| scipy | 未安装 | 需复核 | 需在构建镜像中复核 | 项目直接运行、测试或构建依赖 |
| SQLAlchemy | 2.0.51 | [SQLAlchemy](https://www.sqlalchemy.org) | MIT | 数据访问与事务 |
| sse-starlette | 3.4.5 | [sse-starlette](https://github.com/sysid/sse-starlette) | BSD-3-Clause | 项目直接运行、测试或构建依赖 |
| uvicorn | 0.49.0 | [uvicorn](https://github.com/Kludex/uvicorn) | BSD-3-Clause | 项目直接运行、测试或构建依赖 |

## 前端 Node.js 直接依赖

| 依赖 | 版本 | 来源 | 声明许可证 | 用途 |
| --- | --- | --- | --- | --- |
| @codemirror/lang-python | 6.2.1 | [@codemirror/lang-python](https://github.com/codemirror/lang-python) | MIT | 项目直接运行、测试或构建依赖 |
| @eslint/js | 10.0.1 | [@eslint/js](https://eslint.org) | MIT | 项目直接运行、测试或构建依赖 |
| @phosphor-icons/react | 2.1.10 | [@phosphor-icons/react](https://phosphoricons.com) | MIT | 项目直接运行、测试或构建依赖 |
| @playwright/test | 1.61.1 | [@playwright/test](https://playwright.dev) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-alert-dialog | 1.1.19 | [@radix-ui/react-alert-dialog](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-dialog | 1.1.17 | [@radix-ui/react-dialog](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-dropdown-menu | 2.1.18 | [@radix-ui/react-dropdown-menu](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-popover | 1.1.17 | [@radix-ui/react-popover](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-tabs | 1.1.15 | [@radix-ui/react-tabs](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @radix-ui/react-toast | 1.2.19 | [@radix-ui/react-toast](https://radix-ui.com/primitives) | MIT | 项目直接运行、测试或构建依赖 |
| @tailwindcss/vite | 4.3.2 | [@tailwindcss/vite](https://tailwindcss.com) | MIT | 项目直接运行、测试或构建依赖 |
| @tanstack/react-query | 5.101.2 | [@tanstack/react-query](https://tanstack.com/query) | MIT | 服务端状态与缓存失效 |
| @testing-library/jest-dom | 6.9.1 | [@testing-library/jest-dom](https://github.com/testing-library/jest-dom#readme) | MIT | 项目直接运行、测试或构建依赖 |
| @testing-library/react | 16.3.2 | [@testing-library/react](https://github.com/testing-library/react-testing-library#readme) | MIT | 项目直接运行、测试或构建依赖 |
| @testing-library/user-event | 14.6.1 | [@testing-library/user-event](https://github.com/testing-library/user-event#readme) | MIT | 项目直接运行、测试或构建依赖 |
| @types/react | 19.2.17 | [@types/react](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react) | MIT | 项目直接运行、测试或构建依赖 |
| @types/react-dom | 19.2.3 | [@types/react-dom](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react-dom) | MIT | 项目直接运行、测试或构建依赖 |
| @uiw/react-codemirror | 4.25.11 | [@uiw/react-codemirror](https://uiwjs.github.io/react-codemirror) | MIT | 项目直接运行、测试或构建依赖 |
| @vitejs/plugin-react | 6.0.3 | [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#readme) | MIT | 项目直接运行、测试或构建依赖 |
| @xyflow/react | 12.11.1 | [@xyflow/react](https://reactflow.dev) | MIT | 项目直接运行、测试或构建依赖 |
| axios | 1.18.1 | [axios](https://axios-http.com) | MIT | 项目直接运行、测试或构建依赖 |
| clsx | 2.1.1 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| dayjs | 1.11.21 | [dayjs](https://day.js.org) | MIT | 项目直接运行、测试或构建依赖 |
| echarts | 6.1.0 | [echarts](https://echarts.apache.org) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| eslint | 10.6.0 | [eslint](https://eslint.org) | MIT | 项目直接运行、测试或构建依赖 |
| eslint-plugin-react-hooks | 7.1.1 | [eslint-plugin-react-hooks](https://react.dev/) | MIT | 项目直接运行、测试或构建依赖 |
| eslint-plugin-react-refresh | 0.5.3 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| eventsource-parser | 3.1.0 | [eventsource-parser](https://github.com/rexxars/eventsource-parser#readme) | MIT | 浏览器 SSE 规范解析 |
| globals | 17.7.0 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| jsdom | 29.1.1 | [jsdom](https://github.com/jsdom/jsdom) | MIT | 项目直接运行、测试或构建依赖 |
| markmap-lib | 0.18.12 | [markmap-lib](https://github.com/markmap/markmap/packages/markmap-lib#readme) | MIT | 项目直接运行、测试或构建依赖 |
| markmap-view | 0.18.12 | [markmap-view](https://github.com/markmap/markmap/packages/markmap-view#readme) | MIT | 项目直接运行、测试或构建依赖 |
| mermaid | 11.16.0 | [mermaid](https://github.com/mermaid-js/mermaid) | MIT | 项目直接运行、测试或构建依赖 |
| motion | 12.42.0 | [motion](https://github.com/motiondivision/motion) | MIT | 项目直接运行、测试或构建依赖 |
| openapi-typescript | 7.13.0 | [openapi-typescript](https://openapi-ts.dev) | MIT | OpenAPI 传输类型生成 |
| pyodide | 0.29.2 | [pyodide](https://github.com/pyodide/pyodide) | MPL-2.0 | 项目直接运行、测试或构建依赖 |
| react | 19.2.7 | [react](https://react.dev/) | MIT | 前端界面 |
| react-dom | 19.2.7 | [react-dom](https://react.dev/) | MIT | React 浏览器渲染 |
| react-markdown | 10.1.0 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| react-router-dom | 7.18.1 | [react-router-dom](https://github.com/remix-run/react-router) | MIT | 项目直接运行、测试或构建依赖 |
| remark-gfm | 4.0.1 | 需复核 | MIT | 项目直接运行、测试或构建依赖 |
| tailwindcss | 4.3.2 | [tailwindcss](https://tailwindcss.com) | MIT | 项目直接运行、测试或构建依赖 |
| typescript | 6.0.3 | [typescript](https://www.typescriptlang.org/) | Apache-2.0 | 项目直接运行、测试或构建依赖 |
| typescript-eslint | 8.62.1 | [typescript-eslint](https://typescript-eslint.io/packages/typescript-eslint) | MIT | 项目直接运行、测试或构建依赖 |
| vite | 8.1.0 | [vite](https://vite.dev) | MIT | 前端构建 |
| vite-plugin-static-copy | 4.1.1 | [vite-plugin-static-copy](https://github.com/sapphi-red/vite-plugin-static-copy#readme) | MIT | 项目直接运行、测试或构建依赖 |
| vitest | 4.1.9 | [vitest](https://vitest.dev) | MIT | 前端测试 |
| zustand | 5.0.14 | [zustand](https://github.com/pmndrs/zustand) | MIT | 轻量客户端状态 |

## 离线评测 Node.js 直接依赖

| 依赖 | 版本 | 来源 | 声明许可证 | 用途 |
| --- | --- | --- | --- | --- |
| promptfoo | 0.121.18 | [promptfoo](https://promptfoo.dev) | MIT | 项目直接运行、测试或构建依赖 |

## AI Worker 镜像专用依赖

| 依赖 | 版本 | 来源 | 声明许可证 | 用途 |
| --- | --- | --- | --- | --- |
| torch | 2.13.0+cpu | [PyTorch](https://github.com/pytorch/pytorch) | BSD-3-Clause | Docling CPU 推理运行时 |
| torchvision | 0.28.0+cpu | [TorchVision](https://github.com/pytorch/vision) | BSD-3-Clause | Docling 视觉模型运行时 |
| websockets | 15.0.1 | [websockets](https://github.com/python-websockets/websockets) | BSD-3-Clause | 讯飞原生图片理解 WebSocket 客户端 |
