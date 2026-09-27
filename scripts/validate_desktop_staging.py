from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def check_file(path: Path, root: Path, issues: list[dict[str, str]], kind: str) -> None:
    if not path.is_file():
        issues.append({"kind": kind, "path": str(path), "message": "missing file"})
    elif not inside(path, root):
        issues.append({"kind": kind, "path": str(path), "message": "outside staging root"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a desktop runtime staging directory before packaging.")
    parser.add_argument("--root", required=True, type=Path, help="candidate self-contained staging root")
    parser.add_argument("--python", required=True, type=Path, help="Python executable inside the staging root")
    parser.add_argument("--node", required=True, type=Path, help="Node executable inside the staging root")
    parser.add_argument("--electron", required=True, type=Path, help="Electron executable inside the staging root")
    parser.add_argument("--json", dest="json_path", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    root = args.root.resolve()
    issues: list[dict[str, str]] = []
    for path, kind in ((args.python, "python"), (args.node, "node"), (args.electron, "electron")):
        check_file(path.resolve(), root, issues, kind)

    cfg = args.python.resolve().parent.parent / "pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip().lower() in {"home", "executable"} and value.strip():
                raw = Path(value.strip())
                if raw.is_absolute() and not inside(raw, root):
                    issues.append({"kind": "pyvenv.cfg", "path": str(cfg), "message": f"external {key.strip()}={value.strip()}"})
    else:
        # The official Windows embeddable distribution intentionally has no pyvenv.cfg.
        # Its pythonXY._pth file is the isolation boundary we can verify instead.
        embed_files = sorted(args.python.resolve().parent.glob("python*._pth"))
        if not embed_files:
            issues.append({"kind": "python-runtime", "path": str(args.python), "message": "neither pyvenv.cfg nor an embeddable python*._pth file is present"})
        for embed_file in embed_files:
            for line in embed_file.read_text(encoding="utf-8", errors="replace").splitlines():
                value = line.strip()
                if value.startswith("/") or (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
                    candidate = Path(value)
                    if not inside(candidate, root):
                        issues.append({"kind": "python._pth", "path": str(embed_file), "message": f"external path={value}"})

    for pth in root.rglob("*.pth"):
        if ".cache" in pth.parts or "__pycache__" in pth.parts:
            continue
        for line in pth.read_text(encoding="utf-8", errors="replace").splitlines():
            value = line.strip()
            if value.startswith("/") or (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
                candidate = Path(value)
                if not inside(candidate, root):
                    issues.append({"kind": ".pth", "path": str(pth), "message": f"external path={value}"})

    report: dict[str, Any] = {
        "scope": "pre-packaging staging preflight",
        "root": str(root),
        "packaging_performed": False,
        "ready": not issues,
        "issues": issues,
        "checked": {"python": str(args.python.resolve()), "node": str(args.node.resolve()), "electron": str(args.electron.resolve())},
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
