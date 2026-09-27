"""Assemble an isolated candidate payload from verified local runtime assets.

This copies an explicit application allowlist, not a developer checkout. The
result remains blocked for distribution until its notices and source are reviewed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "desktop_prepare.py", "desktop_runtime.py", "desktop_host_bridge.py", "desktop_worker.py",
    "desktop_search.py",
)
EXCLUDED = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", "node_modules", ".cache"}
SEARXNG_COMMIT = "12f8b6515ca77c3c3bc1498584950ef5daca1433"


def freeze_search_version(output: Path) -> None:
    """Use upstream's frozen-version hook without a runtime Git dependency."""
    values = {
        "VERSION_STRING": f"{SEARXNG_COMMIT[:12]}+edunova",
        "VERSION_TAG": SEARXNG_COMMIT,
        "DOCKER_TAG": f"{SEARXNG_COMMIT[:12]}-edunova",
        "GIT_URL": "https://github.com/searxng/searxng",
        "GIT_BRANCH": SEARXNG_COMMIT,
    }
    content = "# SPDX-License-Identifier: AGPL-3.0-or-later\n"
    content += "# Generated for the pinned EduNova source archive; not an upstream release tag.\n"
    content += "".join(f"{key} = {value!r}\n" for key, value in values.items())
    (output / "app/vendor/searxng/searx/version_frozen.py").write_text(content, encoding="utf-8")
    (output / "sources/searxng/version_frozen.py").write_text(content, encoding="utf-8")


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Missing source directory: {source}")
    for filename in source.rglob("*"):
        relative = filename.relative_to(source)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if filename.is_symlink():
            raise ValueError(f"Unexpected symlink: {filename}")
        if not filename.is_file():
            continue
        if filename.name.startswith(".env") or filename.suffix.lower() in {".pyc", ".pyo", ".log"}:
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filename, destination)


def manifest(root: Path) -> dict:
    files = []
    for filename in sorted(root.rglob("*")):
        if not filename.is_file() or filename.name == "payload-manifest.json":
            continue
        with filename.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": filename.relative_to(root).as_posix(),
                      "bytes": filename.stat().st_size, "sha256": digest})
    result = {"schemaVersion": 1, "redistributionReviewed": False, "files": files}
    (root / "payload-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return {"files": len(files), "bytes": sum(item["bytes"] for item in files),
            "redistributionReviewed": False, "root": str(root)}


def relocate_long_notices(root: Path) -> list[dict]:
    """Preserve notice bytes under short paths usable by the NSIS extractor."""
    index = root / "notices/relocated-license-paths.json"
    entries = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
    for filename in sorted((root / "runtime").rglob("*")):
        if not filename.is_file():
            continue
        relative = filename.relative_to(root).as_posix()
        if len(relative) <= 160 or ".dist-info/licenses/" not in relative:
            continue
        raw = filename.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        identifier = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20]
        target = root / "notices/python" / (identifier + "-" + filename.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"Relocated notice already exists: {target}")
        filename.rename(target)
        entries.append({"originalPath": relative, "installedPath": target.relative_to(root).as_posix(),
                        "sha256": digest, "bytes": len(raw)})
    if entries:
        index.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Remove only empty ancestors left by relocation; retain all other files.
        for entry in entries:
            directory = (root / entry["originalPath"]).parent
            while directory != root / "runtime" and directory.is_relative_to(root / "runtime"):
                try:
                    directory.rmdir()
                except OSError:
                    break
                directory = directory.parent
    return entries


def include_search(output: Path, verified_assets: Path) -> None:
    runtime = output / "runtime/search-python"
    if runtime.exists():
        raise ValueError("Search runtime is already assembled")
    runtime.mkdir()
    for filename in (output / "runtime/python").iterdir():
        if filename.is_file():
            shutil.copy2(filename, runtime / filename.name)
    copy_tree(verified_assets / "search-venv/Lib/site-packages", runtime / "Lib/site-packages")
    source = verified_assets / "searxng-12f8b6515ca77c3c3bc1498584950ef5daca1433"
    target = output / "app/vendor/searxng"
    copy_tree(source / "searx", target / "searx")
    for name in ("LICENSE", "AUTHORS.rst", "README.rst"):
        shutil.copy2(source / name, target / name)
    sources = output / "sources/searxng"
    sources.mkdir(parents=True)
    shutil.copy2(verified_assets / "searxng-12f8b65.zip", sources / "searxng-12f8b65.zip")
    shutil.copy2(source / "searx/valkeydb.py", sources / "valkeydb.py")
    (sources / "MODIFICATIONS.md").write_text(
        "# Windows adaptation\n\n"
        "Upstream commit: 12f8b6515ca77c3c3bc1498584950ef5daca1433.\n"
        "Source: https://github.com/searxng/searxng\n\n"
        "The accompanying valkeydb.py guards the POSIX pwd import and logs a "
        "Windows connection failure without calling pwd.getpwuid. "
        "The original source archive and complete modified file are included.\n"
        "version_frozen.py records this pinned commit using upstream's frozen-version "
        "hook, so launching the desktop application does not require Git.\n",
        encoding="utf-8",
    )
    freeze_search_version(output)


def include_verifier(output: Path) -> None:
    target = output / "app/verifier"
    (target / "runtime").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "code-verifier/policy.mjs", target / "policy.mjs")
    source = REPO / "code-verifier/node_modules/pyodide"
    for name in ("pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "package.json"):
        shutil.copy2(source / name, target / "runtime" / name)
    for filename in source.iterdir():
        if filename.is_file() and filename.name.lower().startswith(("license", "notice")):
            shutil.copy2(filename, target / "runtime" / filename.name)


def assemble(staging: Path, output: Path, sources: Path | None = None) -> dict:
    if not staging.is_absolute() or not output.is_absolute():
        raise ValueError("Use absolute input and output directories")
    staging, output = staging.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Output must be a new directory; existing candidate/data is never overwritten")
    if output.is_relative_to(staging) or staging.is_relative_to(output):
        raise ValueError("Input and output directories must be separate")
    python = staging / "runtime/python-独立 验证"
    redis_candidates = list((staging / "runtime/redis").rglob("redis-server.exe"))
    if len(redis_candidates) != 1:
        raise ValueError("Expected exactly one verified Redis runtime")
    if not (python / "python.exe").is_file():
        raise ValueError("Verified embedded Python is missing")
    output.mkdir(parents=True)
    for name, source in (
        ("python", python), ("node", staging / "runtime/node"),
        ("postgresql", staging / "runtime/postgresql"), ("redis", redis_candidates[0].parent),
    ):
        copy_tree(source, output / "runtime" / name)
    copy_tree(staging / "models", output / "models")
    copy_tree(staging / "app/frontend", output / "app/frontend")
    copy_tree(REPO / "backend/app", output / "app/backend/app")
    copy_tree(REPO / "backend/migrations", output / "app/backend/migrations")
    shutil.copy2(REPO / "alembic.ini", output / "app/alembic.ini")
    (output / "app/scripts").mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy2(REPO / "scripts" / name, output / "app/scripts" / name)
    include_search(output, staging.parent)
    include_verifier(output)
    (output / "notices").mkdir()
    shutil.copy2(REPO / "THIRD_PARTY_NOTICES.md", output / "notices/THIRD_PARTY_NOTICES.md")
    shutil.copy2(REPO / "docs/DEPENDENCY_LICENSES.md", output / "notices/DEPENDENCY_LICENSES.md")
    if sources:
        copy_tree(sources.resolve() / "sources", output / "sources/redis")
        for name in ("source-inventory.json", "build-redis-8.10.2.yml"):
            shutil.copy2(sources / name, output / "sources/redis" / name)
    relocate_long_notices(output)
    return manifest(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--redis-sources", type=Path)
    args = parser.parse_args()
    print(json.dumps(assemble(args.staging, args.output, args.redis_sources), ensure_ascii=False))
