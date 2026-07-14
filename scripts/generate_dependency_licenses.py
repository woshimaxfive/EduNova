from __future__ import annotations

from importlib import metadata
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "DEPENDENCY_LICENSES.md"


def python_dependencies() -> list[tuple[str, str, str]]:
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
            rows.append((name, metadata.version(name), package.get("License-Expression") or package.get("License") or "需复核"))
        except metadata.PackageNotFoundError:
            rows.append((name, "未安装", "需在构建镜像中复核"))
    return rows


def node_dependencies(package_dir: Path) -> list[tuple[str, str, str]]:
    package_json = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    names = set(package_json.get("dependencies", {})) | set(package_json.get("devDependencies", {}))
    rows = []
    for name in sorted(names, key=str.casefold):
        installed_package = package_dir / "node_modules" / name / "package.json"
        if not installed_package.exists():
            rows.append((name, "未安装", "需在构建环境中复核"))
            continue
        details = json.loads(installed_package.read_text(encoding="utf-8"))
        license_value = details.get("license", "需复核")
        if isinstance(license_value, dict):
            license_value = license_value.get("type", "需复核")
        rows.append((name, str(details.get("version", "需复核")), str(license_value)))
    return rows


def docker_only_dependencies() -> list[tuple[str, str, str]]:
    return [
        ("torch", "2.13.0+cpu", "需在 AI Worker 镜像中复核"),
        ("torchvision", "0.28.0+cpu", "需在 AI Worker 镜像中复核"),
    ]


def main() -> None:
    lines = [
        "# 直接依赖许可证清单",
        "",
        "本文件由 `scripts/generate_dependency_licenses.py` 从固定依赖和本地包元数据生成；传递依赖由供应链门禁继续扫描。",
        "",
        "| Python 依赖 | 版本 | 声明许可证 |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {name} | {version} | {license_name.replace('|', '/')} |" for name, version, license_name in python_dependencies())
    for title, package_dir in (
        ("前端 Node.js 直接依赖", ROOT / "frontend"),
        ("离线评测 Node.js 直接依赖", ROOT / "evals" / "promptfoo"),
    ):
        lines.extend(("", f"## {title}", "", "| 依赖 | 版本 | 声明许可证 |", "| --- | --- | --- |"))
        lines.extend(
            f"| {name} | {version} | {license_name.replace('|', '/')} |"
            for name, version, license_name in node_dependencies(package_dir)
        )
    lines.extend(("", "## AI Worker 镜像专用依赖", "", "| 依赖 | 版本 | 声明许可证 |", "| --- | --- | --- |"))
    lines.extend(
        f"| {name} | {version} | {license_name.replace('|', '/')} |"
        for name, version, license_name in docker_only_dependencies()
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
