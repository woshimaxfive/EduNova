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
}


def _purpose(name: str) -> str:
    return PURPOSES.get(name.casefold(), "项目直接运行、测试或构建依赖")


def _clean_cell(value: object, limit: int = 160) -> str:
    return " ".join(str(value or "需复核").replace("|", "/").split())[:limit]


def _source_link(name: str, url: str) -> str:
    safe_url = url.strip()
    return f"[{name}]({safe_url})" if safe_url.startswith(("https://", "http://")) else "需复核"


def _project_urls(package: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in package.get_all("Project-URL") or []:
        label, separator, url = item.partition(",")
        if separator and url.strip():
            result[label.strip()] = url.strip()
    return result


def python_dependencies() -> list[tuple[str, str, str, str, str]]:
    names: set[str] = set()
    for filename in (
        "requirements.txt",
        "requirements-ai.txt",
        "requirements-dev.txt",
        "requirements-eval-network.txt",
    ):
        for line in (ROOT / "backend" / filename).read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value or value.startswith(("#", "-r")):
                continue
            names.add(re.split(r"[<>=!~\[]", value, maxsplit=1)[0].strip())
    rows = []
    for name in sorted(names, key=str.casefold):
        try:
            package = metadata.metadata(name)
            project_urls = _project_urls(package)
            source = project_urls.get("Source") or project_urls.get("Repository") or package.get("Home-page") or ""
            rows.append(
                (
                    name,
                    metadata.version(name),
                    _source_link(name, source),
                    _clean_cell(package.get("License-Expression") or package.get("License") or "需复核"),
                    _purpose(name),
                )
            )
        except metadata.PackageNotFoundError:
            rows.append((name, "未安装", "需复核", "需在构建镜像中复核", _purpose(name)))
    return rows


def node_dependencies(package_dir: Path) -> list[tuple[str, str, str, str, str]]:
    package_json = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    names = set(package_json.get("dependencies", {})) | set(package_json.get("devDependencies", {}))
    rows = []
    for name in sorted(names, key=str.casefold):
        installed_package = package_dir / "node_modules" / name / "package.json"
        if not installed_package.exists():
            rows.append((name, "未安装", "需复核", "需在构建环境中复核", _purpose(name)))
            continue
        details = json.loads(installed_package.read_text(encoding="utf-8"))
        license_value = details.get("license", "需复核")
        if isinstance(license_value, dict):
            license_value = license_value.get("type", "需复核")
        repository = details.get("repository")
        repository_url = repository.get("url", "") if isinstance(repository, dict) else str(repository or "")
        repository_url = repository_url.removeprefix("git+").removesuffix(".git")
        source = str(details.get("homepage") or repository_url)
        rows.append(
            (
                name,
                str(details.get("version", "需复核")),
                _source_link(name, source),
                _clean_cell(license_value),
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
        "本文件由 `scripts/generate_dependency_licenses.py` 从固定依赖和本地包元数据生成；传递依赖由供应链门禁继续扫描。",
        "",
        "| Python 依赖 | 版本 | 来源 | 声明许可证 | 用途 |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {name} | {version} | {source} | {license_name} | {purpose} |" for name, version, source, license_name, purpose in python_dependencies())
    for title, package_dir in (
        ("前端 Node.js 直接依赖", ROOT / "frontend"),
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
