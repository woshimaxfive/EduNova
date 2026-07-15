from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "backend" / "openapi.json"
TYPES_PATH = ROOT / "frontend" / "src" / "types" / "openapi.generated.ts"
sys.path.insert(0, str(ROOT))

candidates = (
    (ROOT / ".venv" / "Scripts" / "python.exe",)
    if os.name == "nt"
    else (ROOT / ".venv" / "bin" / "python",)
)
interpreter = next((path.resolve() for path in candidates if path.exists()), None)
if interpreter is not None and Path(sys.executable).resolve() != interpreter:
    raise SystemExit(subprocess.call([str(interpreter), __file__]))

from backend.app.main import app  # noqa: E402


def _openapi_text() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    expected_openapi = _openapi_text()
    if not OPENAPI_PATH.exists() or OPENAPI_PATH.read_text(encoding="utf-8") != expected_openapi:
        print("OpenAPI JSON 已漂移，请运行：pnpm --dir frontend openapi:generate", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="edunova-openapi-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        temporary_openapi = temporary_root / "openapi.json"
        temporary_types = temporary_root / "openapi.generated.ts"
        temporary_openapi.write_text(expected_openapi, encoding="utf-8")
        command = [
            "pnpm.cmd" if os.name == "nt" else "pnpm",
            "exec",
            "openapi-typescript",
            str(temporary_openapi),
            "-o",
            str(temporary_types),
        ]
        result = subprocess.run(command, cwd=ROOT / "frontend", check=False)
        if result.returncode != 0:
            return result.returncode
        if not TYPES_PATH.exists() or TYPES_PATH.read_text(encoding="utf-8") != temporary_types.read_text(encoding="utf-8"):
            print("前端 OpenAPI 类型已漂移，请运行：pnpm --dir frontend openapi:generate", file=sys.stderr)
            return 1

    print("OpenAPI JSON 与前端传输类型一致，检查过程未修改工作区。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
