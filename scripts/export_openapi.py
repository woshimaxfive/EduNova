from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend" / "openapi.json"
sys.path.insert(0, str(ROOT))

candidates = (
    ROOT / ".venv" / "Scripts" / "python.exe",
    ROOT / ".venv" / "bin" / "python",
)
interpreter = next((path.resolve() for path in candidates if path.exists()), None)
if interpreter is not None and Path(sys.executable).resolve() != interpreter:
    os.execv(str(interpreter), [str(interpreter), __file__])

from backend.app.main import app  # noqa: E402


def main() -> None:
    OUTPUT.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
