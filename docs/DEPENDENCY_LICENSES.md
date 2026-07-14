# 直接依赖许可证清单

本文件由 `scripts/generate_dependency_licenses.py` 从固定依赖和本地包元数据生成；传递依赖由供应链门禁继续扫描。

| Python 依赖 | 版本 | 声明许可证 |
| --- | --- | --- |
| alembic | 1.18.5 | MIT |
| bcrypt | 5.0.0 | Apache-2.0 |
| boto3 | 1.43.47 | Apache-2.0 |
| cryptography | 49.0.0 | Apache-2.0 OR BSD-3-Clause |
| docling-slim | 2.113.0 | MIT |
| fastapi | 0.138.2 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| json-repair | 0.61.4 | MIT |
| langgraph | 1.2.7 | MIT |
| openai | 2.45.0 | Apache-2.0 |
| opencv-python-headless | 未安装 | 需在构建镜像中复核 |
| opentelemetry-exporter-otlp-proto-http | 1.43.0 | Apache-2.0 |
| opentelemetry-instrumentation-fastapi | 0.64b0 | Apache-2.0 |
| opentelemetry-instrumentation-httpx | 0.64b0 | Apache-2.0 |
| opentelemetry-instrumentation-redis | 0.64b0 | Apache-2.0 |
| opentelemetry-instrumentation-sqlalchemy | 0.64b0 | Apache-2.0 |
| opentelemetry-sdk | 1.43.0 | Apache-2.0 |
| pgvector | 0.4.2 | MIT |
| pip-audit | 2.10.1 | 需复核 |
| psycopg | 3.3.4 | LGPL-3.0-only |
| puremagic | 2.2.0 | MIT |
| pydantic-settings | 2.14.2 | MIT |
| PyJWT | 2.13.0 | MIT |
| pypdf | 6.14.2 | BSD-3-Clause |
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| python-docx | 1.2.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| python-pptx | 1.0.2 | MIT |
| ragas | 未安装 | 需在构建镜像中复核 |
| redis | 8.0.1 | MIT |
| reportlab | 5.0.0 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. |
| rq | 2.10.0 | BSD-2-Clause |
| ruff | 0.15.20 | MIT |
| scipy | 未安装 | 需在构建镜像中复核 |
| SQLAlchemy | 2.0.51 | MIT |
| sse-starlette | 3.4.5 | BSD-3-Clause |
| uvicorn | 0.49.0 | BSD-3-Clause |

## 前端 Node.js 直接依赖

| 依赖 | 版本 | 声明许可证 |
| --- | --- | --- |
| @codemirror/lang-python | 6.2.1 | MIT |
| @eslint/js | 10.0.1 | MIT |
| @phosphor-icons/react | 2.1.10 | MIT |
| @playwright/test | 1.61.1 | Apache-2.0 |
| @radix-ui/react-alert-dialog | 1.1.19 | MIT |
| @radix-ui/react-dialog | 1.1.17 | MIT |
| @radix-ui/react-dropdown-menu | 2.1.18 | MIT |
| @radix-ui/react-popover | 1.1.17 | MIT |
| @radix-ui/react-tabs | 1.1.15 | MIT |
| @radix-ui/react-toast | 1.2.19 | MIT |
| @tailwindcss/vite | 4.3.2 | MIT |
| @tanstack/react-query | 5.101.2 | MIT |
| @testing-library/jest-dom | 6.9.1 | MIT |
| @testing-library/react | 16.3.2 | MIT |
| @testing-library/user-event | 14.6.1 | MIT |
| @types/react | 19.2.17 | MIT |
| @types/react-dom | 19.2.3 | MIT |
| @uiw/react-codemirror | 4.25.11 | MIT |
| @vitejs/plugin-react | 6.0.3 | MIT |
| @xyflow/react | 12.11.1 | MIT |
| axios | 1.18.1 | MIT |
| clsx | 2.1.1 | MIT |
| dayjs | 1.11.21 | MIT |
| echarts | 6.1.0 | Apache-2.0 |
| eslint | 10.6.0 | MIT |
| eslint-plugin-react-hooks | 7.1.1 | MIT |
| eslint-plugin-react-refresh | 0.5.3 | MIT |
| eventsource-parser | 3.1.0 | MIT |
| globals | 17.7.0 | MIT |
| jsdom | 29.1.1 | MIT |
| markmap-lib | 0.18.12 | MIT |
| markmap-view | 0.18.12 | MIT |
| mermaid | 11.16.0 | MIT |
| motion | 12.42.0 | MIT |
| openapi-typescript | 7.13.0 | MIT |
| pyodide | 0.29.2 | MPL-2.0 |
| react | 19.2.7 | MIT |
| react-dom | 19.2.7 | MIT |
| react-markdown | 10.1.0 | MIT |
| react-router-dom | 7.18.1 | MIT |
| remark-gfm | 4.0.1 | MIT |
| tailwindcss | 4.3.2 | MIT |
| typescript | 6.0.3 | Apache-2.0 |
| typescript-eslint | 8.62.1 | MIT |
| vite | 8.1.0 | MIT |
| vite-plugin-static-copy | 4.1.1 | MIT |
| vitest | 4.1.9 | MIT |
| zustand | 5.0.14 | MIT |

## 离线评测 Node.js 直接依赖

| 依赖 | 版本 | 声明许可证 |
| --- | --- | --- |
| promptfoo | 0.121.18 | MIT |

## AI Worker 镜像专用依赖

| 依赖 | 版本 | 声明许可证 |
| --- | --- | --- |
| torch | 2.13.0+cpu | 需在 AI Worker 镜像中复核 |
| torchvision | 0.28.0+cpu | 需在 AI Worker 镜像中复核 |
