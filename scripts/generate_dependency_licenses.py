from __future__ import annotations

from importlib import metadata
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "DEPENDENCY_LICENSES.md"

PURPOSES = {
    "fastapi": "后端 API 与 OpenAPI",
    "sqlalchemy": "数据访问与事务",
    "alembic": "数据库迁移",
    "langgraph": "学习闭环状态图编排",
    "langchain-core": "消息裁剪与受控工具接口",
    "docling": "PDF、DOCX、PPTX 通用结构提取",
    "openai": "OpenAI-compatible 模型协议适配",
    "opentelemetry-api": "通用可观测性 API",
    "react": "前端界面",
    "react-dom": "React 浏览器渲染",
    "@tanstack/react-query": "服务端状态与缓存失效",
    "openapi-typescript": "OpenAPI 传输类型生成",
    "eventsource-parser": "浏览器 SSE 规范解析",
    "zustand": "轻量客户端状态",
    "vite": "前端构建",
    "vitest": "前端测试",
    "setuptools": "AI worker 的 PyTorch 运行依赖；固定安全版本",
    "electron": "Windows 桌面宿主；捆绑组件另有第三方通知",
    "pywin32": "Windows 桌面进程生命周期与 Job Objects",
    "fastembed": "本地 CPU 向量推理",
    "onnxruntime": "本地 ONNX 模型运行时",
}

PACKAGE_METADATA_OVERRIDES = {
    "sherpa-onnx": ("https://github.com/k2-fsa/sherpa-onnx", "Apache-2.0 source; 1.x wheels bundle GPL components; see docs/LOCAL_SPEECH.md"),
    "sherpa-onnx-core": ("https://github.com/k2-fsa/sherpa-onnx", "Apache-2.0 source; 1.x wheels bundle GPL components; see docs/LOCAL_SPEECH.md"),
    "setuptools": ("https://github.com/pypa/setuptools", "MIT"),
    "bcrypt": ("https://github.com/pyca/bcrypt", "Apache-2.0"),
    "cryptography": ("https://github.com/pyca/cryptography", "Apache-2.0 OR BSD-3-Clause"),
    "docling-slim": ("https://github.com/docling-project/docling", "MIT"),
    "json-repair": ("https://github.com/mangiucugna/json_repair", "MIT"),
    "opencv-python-headless": (
        "https://github.com/opencv/opencv-python",
        "MIT build scripts; bundled OpenCV Apache-2.0; bundled third-party licenses vary",
    ),
    "pgvector": ("https://github.com/pgvector/pgvector-python", "MIT"),
    "pip-audit": ("https://github.com/pypa/pip-audit", "Apache-2.0"),
    "psycopg": ("https://github.com/psycopg/psycopg", "LGPL-3.0-only"),
    "puremagic": ("https://github.com/cdgriffith/puremagic", "MIT"),
    "pyjwt": ("https://github.com/jpadilla/pyjwt", "MIT"),
    "pytest-asyncio": ("https://github.com/pytest-dev/pytest-asyncio", "Apache-2.0"),
    "ragas": ("https://github.com/vibrantlabsai/ragas", "Apache-2.0"),
    "redis": ("https://github.com/redis/redis-py", "MIT"),
    "rq": ("https://github.com/rq/rq", "BSD-2-Clause"),
    "scipy": ("https://github.com/scipy/scipy", "BSD-3-Clause"),
    "websockets": ("https://github.com/python-websockets/websockets", "BSD-3-Clause"),
    # Checked against the v0.23.2 upstream LICENSE; wheel metadata omits License.
    "tokenizers": ("https://github.com/huggingface/tokenizers", "Apache-2.0"),
    "clsx": ("https://github.com/lukeed/clsx", "MIT"),
    "eslint-plugin-react-refresh": ("https://github.com/ArnaudBarre/eslint-plugin-react-refresh", "MIT"),
    "globals": ("https://github.com/sindresorhus/globals", "MIT"),
    "react-markdown": ("https://github.com/remarkjs/react-markdown", "MIT"),
    "remark-gfm": ("https://github.com/remarkjs/remark-gfm", "MIT"),
}


def _purpose(name: str) -> str:
    return PURPOSES.get(name.casefold(), "项目直接运行、测试或构建依赖")


def _clean_cell(value: object, limit: int = 160) -> str:
    return " ".join(str(value or "需复核").replace("|", "/").split())[:limit]


def _source_link(name: str, url: str) -> str:
    safe_url = url.strip()
    return f"[{name}]({safe_url})" if safe_url.startswith(("https://", "http://")) else "需复核"


def _resolved_metadata(name: str, source: str, license_name: object) -> tuple[str, str]:
    override = PACKAGE_METADATA_OVERRIDES.get(name.casefold())
    if override:
        source, license_name = override
    return _source_link(name, source), _clean_cell(license_name)


def _project_urls(package: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in package.get_all("Project-URL") or []:
        label, separator, url = item.partition(",")
        if separator and url.strip():
            result[label.strip()] = url.strip()
    return result


def _declared_requirement(value: str) -> tuple[str, str]:
    """Return a requirement name and its exact declared version when available."""
    match = re.match(
        r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]+\])?\s*==\s*([^;#\s]+)",
        value,
    )
    if match:
        return match.group(1), match.group(2)
    return re.split(r"[<>=!~\[]", value, maxsplit=1)[0].strip(), "未固定"


def python_dependencies() -> list[tuple[str, str, str, str, str]]:
    names: set[str] = set()
    declared_versions: dict[str, str] = {}
    for filename in (
        "requirements.txt",
        "requirements-ai.txt",
        "requirements-dev.txt",
        "requirements-eval-network.txt",
        "requirements-local-speech.txt",
        "requirements-local-embedding.txt",
        "requirements-desktop.txt",
    ):
        for line in (ROOT / "backend" / filename).read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value or value.startswith(("#", "-r")):
                continue
            name, version = _declared_requirement(value)
            names.add(name)
            declared_versions[name.casefold()] = version
    rows = []
    for name in sorted(names, key=str.casefold):
        declared_version = declared_versions.get(name.casefold(), "未固定")
        try:
            package = metadata.metadata(name)
            project_urls = _project_urls(package)
            source = (project_urls.get("Source") or project_urls.get("Repository")
                      or project_urls.get("Homepage") or package.get("Home-page") or "")
            source_link, license_name = _resolved_metadata(
                name,
                source,
                package.get("License-Expression") or package.get("License") or "需复核",
            )
            rows.append(
                (
                    name,
                    declared_version,
                    source_link,
                    license_name,
                    _purpose(name),
                )
            )
        except metadata.PackageNotFoundError:
            source_link, license_name = _resolved_metadata(name, "", "需在构建镜像中复核")
            rows.append((name, declared_version, source_link, license_name, _purpose(name)))
    return rows


def node_dependencies(package_dir: Path) -> list[tuple[str, str, str, str, str]]:
    package_json = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    names = set(package_json.get("dependencies", {})) | set(package_json.get("devDependencies", {}))
    rows = []
    for name in sorted(names, key=str.casefold):
        installed_package = package_dir / "node_modules" / name / "package.json"
        if not installed_package.exists():
            source_link, license_name = _resolved_metadata(name, "", "需在构建环境中复核")
            rows.append((name, "未安装", source_link, license_name, _purpose(name)))
            continue
        details = json.loads(installed_package.read_text(encoding="utf-8"))
        license_value = details.get("license", "需复核")
        if isinstance(license_value, dict):
            license_value = license_value.get("type", "需复核")
        repository = details.get("repository")
        repository_url = repository.get("url", "") if isinstance(repository, dict) else str(repository or "")
        repository_url = repository_url.removeprefix("git+").removesuffix(".git")
        source = str(details.get("homepage") or repository_url)
        source_link, license_name = _resolved_metadata(name, source, license_value)
        rows.append(
            (
                name,
                str(details.get("version", "需复核")),
                source_link,
                license_name,
                _purpose(name),
            )
        )
    return rows


def docker_only_dependencies() -> list[tuple[str, str, str, str, str]]:
    return [
        ("torch", "2.13.0+cpu", "[PyTorch](https://github.com/pytorch/pytorch)", "BSD-3-Clause", "Docling CPU 推理运行时"),
        ("torchvision", "0.28.0+cpu", "[TorchVision](https://github.com/pytorch/vision)", "BSD-3-Clause", "Docling 视觉模型运行时"),
    ]


def main() -> None:
    lines = [
        "# 直接依赖许可证清单",
        "",
        "本文件由 `scripts/generate_dependency_licenses.py` 从依赖声明、本地包元数据和已核对的项目元数据生成；传递依赖由供应链检查继续扫描。版本直接取自对应 requirements 文件；标记为“未固定”的依赖需要在发布前明确版本。",
        "",
        "| Python 依赖 | 版本 | 来源 | 声明许可证 | 用途 |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {name} | {version} | {source} | {license_name} | {purpose} |" for name, version, source, license_name, purpose in python_dependencies())
    for title, package_dir in (
        ("前端 Node.js 直接依赖", ROOT / "frontend"),
        ("代码验证 Node.js 直接依赖", ROOT / "code-verifier"),
        ("桌面宿主 Node.js 直接依赖", ROOT / "desktop"),
        ("离线评测 Node.js 直接依赖", ROOT / "evals" / "promptfoo"),
    ):
        lines.extend(("", f"## {title}", "", "| 依赖 | 版本 | 来源 | 声明许可证 | 用途 |", "| --- | --- | --- | --- | --- |"))
        lines.extend(
            f"| {name} | {version} | {source} | {license_name} | {purpose} |"
            for name, version, source, license_name, purpose in node_dependencies(package_dir)
        )
    lines.extend(("", "## AI Worker 镜像专用依赖", "", "| 依赖 | 版本 | 来源 | 声明许可证 | 用途 |", "| --- | --- | --- | --- | --- |"))
    lines.extend(
        f"| {name} | {version} | {source} | {license_name} | {purpose} |"
        for name, version, source, license_name, purpose in docker_only_dependencies()
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
