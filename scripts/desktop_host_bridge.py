"""Trusted desktop host JSON-lines lifecycle bridge; no renderer-supplied commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ALLOWED_METHODS = {"status", "start", "stop"}
MAX_MESSAGE = 4096


def response(request_id, *, result=None, error=None):
    payload = {"id": request_id, "ok": error is None}
    payload["result" if error is None else "error"] = result if error is None else error
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class HostBridge:
    def __init__(self, manifest: Path, controller: Path, python: Path):
        self.manifest = manifest.resolve()
        self.controller = controller.resolve()
        self.python = python.resolve()
        self.process = None
        self.reader = None
        if not self.manifest.is_file():
            raise ValueError("manifest is not a file")
        if not self.controller.is_file() or not self.python.is_file():
            raise ValueError("controller runtime is unavailable")

    def command(self, method, wait_seconds):
        return [
            str(self.python),
            "-B",
            "-X",
            "utf8",
            str(self.controller),
            method,
            "--manifest",
            str(self.manifest),
            "--wait-seconds",
            str(wait_seconds),
        ]

    def close(self, wait_seconds):
        if self.process is not None:
            # EOF goes only to the controller owned by this bridge. Never stop
            # another host's runtime merely because it uses the same manifest.
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=wait_seconds)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Owned Popen handle; controller jobs close.
                self.process.wait(timeout=10)
            if self.reader is not None:
                self.reader.join(timeout=2)
                self.reader = None
            self.process.stdout.close()
            self.process = None

    def call(self, method: str, wait_seconds: float):
        if method not in ALLOWED_METHODS:
            raise ValueError("unsupported lifecycle method")
        if method == "stop":
            self.close(wait_seconds)
            return {"phase": "stopped", "scope": "owned_runtime"}
        if method == "start":
            if self.process is not None and self.process.poll() is None:
                return {"phase": "running", "already_owned": True}
            self.close(wait_seconds)
            ready = threading.Event()
            try:
                self.process = subprocess.Popen(
                    self.command("start", wait_seconds) + ["--host-stdin"],
                    cwd=self.manifest.parent,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32"
                    else 0,
                )

                def read_controller():
                    # Drain all output without forwarding local diagnostics to
                    # the window. Only the owned controller's ready line counts.
                    while True:
                        line = self.process.stdout.readline(MAX_MESSAGE + 1)
                        if not line:
                            return
                        if len(line) > MAX_MESSAGE:
                            continue
                        try:
                            message = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        if (
                            isinstance(message, dict)
                            and message.get("phase") == "running"
                        ):
                            ready.set()

                self.reader = threading.Thread(target=read_controller, daemon=True)
                self.reader.start()
                deadline = time.monotonic() + wait_seconds
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError(
                            "runtime startup failed; inspect local runtime state"
                        )
                    if ready.wait(0.05):
                        return {"phase": "running"}
                raise RuntimeError("runtime startup deadline exceeded")
            except BaseException:
                self.close(wait_seconds)
                raise
        completed = subprocess.run(
            self.command("status", wait_seconds),
            cwd=self.manifest.parent,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=wait_seconds + 5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if completed.returncode:
            raise RuntimeError(
                "runtime status unavailable; inspect local configuration"
            )
        state = json.loads(completed.stdout)
        # Deliberately do not expose local paths, PIDs, command details or logs.
        return {
            "active": bool(state.get("active")),
            "phase": state.get("phase", "unknown"),
            "owned": self.process is not None and self.process.poll() is None,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trusted-host JSON-lines lifecycle bridge"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--controller", default=str(Path(__file__).with_name("desktop_runtime.py"))
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--wait-seconds", type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.wait_seconds <= 300:
        parser.error("--wait-seconds must be between 0 and 300")
    try:
        bridge = HostBridge(
            Path(args.manifest), Path(args.controller), Path(args.python)
        )
    except (OSError, ValueError):
        print(response(None, error="host configuration unavailable"), flush=True)
        return 2
    try:
        while True:
            line = sys.stdin.readline(MAX_MESSAGE + 1)
            if not line:
                break
            request_id = None
            try:
                if len(line) > MAX_MESSAGE:
                    print(response(None, error="message too large"), flush=True)
                    return 2
                request = json.loads(line)
                if isinstance(request, dict) and type(request.get("id")) in (
                    str,
                    int,
                    type(None),
                ):
                    request_id = request.get("id")
                if not isinstance(request, dict) or set(request) - {"id", "method"}:
                    raise ValueError("request must contain only id and method")
                request_id = request.get("id")
                if type(request_id) not in (str, int, type(None)):
                    request_id = None
                    raise ValueError("invalid request id")
                method = request.get("method")
                if not isinstance(method, str):
                    raise ValueError("request must contain only id and method")
                result = bridge.call(method, args.wait_seconds)
                print(response(request_id, result=result), flush=True)
            except json.JSONDecodeError:
                print(response(None, error="invalid JSON"), flush=True)
            except (
                OSError,
                ValueError,
                RuntimeError,
                subprocess.TimeoutExpired,
            ) as exc:
                error = (
                    str(exc)
                    if isinstance(exc, (ValueError, RuntimeError))
                    else "runtime operation failed"
                )
                print(response(request_id, error=error), flush=True)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        bridge.close(args.wait_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
