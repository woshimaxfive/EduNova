"""Windows service controller for the unpackaged EduNova desktop runtime.

Start remains in the foreground so the desktop host can own its lifetime.
Only trusted local manifests are supported. Job Objects control lifecycle,
not filesystem/network isolation. No stored PID is used to terminate a process.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import threading
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

if os.name == "nt":
    import win32api
    import win32con
    import win32event
    import win32job


class RuntimeErrorState(RuntimeError):
    """A startup or lifecycle failure, without secret command arguments."""


class StopRequested(Exception):
    pass


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def read_manifest(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("services"), list)
        or not value["services"]
    ):
        raise RuntimeErrorState("manifest needs a non-empty services list")
    names = set()
    ports = set()
    for item in value["services"]:
        if not isinstance(item, dict) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", str(item.get("name", ""))
        ):
            raise RuntimeErrorState(
                "service name must contain only letters, digits, underscores or hyphens"
            )
        if item["name"] in names:
            raise RuntimeErrorState("duplicate service name")
        names.add(item["name"])
        for field in ("command", "ready_command", "stop_command"):
            command = item.get(field)
            if command is None and field != "command":
                continue
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(x, str) for x in command)
            ):
                raise RuntimeErrorState(f"invalid {field}: {item['name']}")
            if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
                raise RuntimeErrorState(
                    f"{field} requires an existing absolute executable: {item['name']}"
                )
        if item.get("mode", "service") not in ("service", "oneshot"):
            raise RuntimeErrorState("mode must be service or oneshot")
        if not isinstance(item.get("env", {}), dict):
            raise RuntimeErrorState("env must be an object")
        for field in ("timeout", "stop_timeout"):
            if field in item and (
                not isinstance(item[field], (int, float)) or not 0 < item[field] <= 300
            ):
                raise RuntimeErrorState(f"{field} must be between 0 and 300 seconds")
        url = item.get("health_url")
        if url:
            parsed = urlsplit(url)
            if (
                parsed.scheme != "http"
                or parsed.hostname != "127.0.0.1"
                or not parsed.port
                or parsed.username
                or parsed.password
            ):
                raise RuntimeErrorState(
                    "health URL must use http://127.0.0.1 with an explicit port"
                )
            item.setdefault("port", parsed.port)
            if item["port"] != parsed.port:
                raise RuntimeErrorState("health URL and service port differ")
        if "port" in item:
            port = item["port"]
            if type(port) is not int or not 1 <= port <= 65535 or port in ports:
                raise RuntimeErrorState(
                    "service ports must be distinct integers between 1 and 65535"
                )
            ports.add(port)
    return value


def state_path(path: Path, manifest: dict) -> Path:
    return (
        path.parent / manifest.get("state_file", ".edunova-runtime/state.json")
    ).resolve()


def object_name(path: Path) -> str:
    digest = hashlib.sha256(
        os.path.normcase(str(path.resolve())).encode("utf-8")
    ).hexdigest()
    return "Local\\EduNovaRuntime-" + digest


@contextmanager
def owned_mutex(path: Path):
    handle = win32event.CreateMutex(None, False, object_name(path))
    acquired = False
    try:
        acquired = win32event.WaitForSingleObject(handle, 0) in (
            win32event.WAIT_OBJECT_0,
            win32event.WAIT_ABANDONED,
        )
        if not acquired:
            raise RuntimeErrorState(
                "runtime already started or another controller is active"
            )
        yield
    finally:
        if acquired:
            win32event.ReleaseMutex(handle)
        handle.Close()


def controller_active(path: Path) -> bool:
    try:
        with owned_mutex(path):
            return False
    except RuntimeErrorState:
        return True


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def health_ok(url: str) -> bool:
    try:
        # Loopback requests must not be redirected or sent via the user's proxy.
        with build_opener(ProxyHandler({}), NoRedirect()).open(
            Request(url), timeout=1
        ) as response:
            return 200 <= response.status < 300
    except OSError:
        return False


class OwnedService:
    def __init__(self, item: dict, root: Path):
        self.item = item
        self.cwd = (root / item.get("cwd", ".")).resolve()
        self.env = os.environ.copy()
        for key, value in item.get("env", {}).items():
            if value is None:
                self.env.pop(key, None)
            else:
                self.env[key] = str(value)
        self.log = None
        self.process = None
        self.job = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(
            self.job, win32job.JobObjectExtendedLimitInformation
        )
        limits["BasicLimitInformation"]["LimitFlags"] |= (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        win32job.SetInformationJobObject(
            self.job, win32job.JobObjectExtendedLimitInformation, limits
        )
        try:
            logfile = root / item.get("log", f".edunova-runtime/{item['name']}.log")
            logfile.parent.mkdir(parents=True, exist_ok=True)
            self.log = logfile.open("a", encoding="utf-8")
        except BaseException:
            self.job.Close()
            raise

    def spawn(self, command: list[str]):
        # Reuse the RQ prototype's stdin gate: no service/descendant can execute
        # until the wrapper belongs to our non-inheritable kill-on-close job.
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(Path(__file__).resolve()),
                "_child",
                *command,
            ],
            cwd=self.cwd,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            handle = win32api.OpenProcess(
                win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE,
                False,
                process.pid,
            )
            try:
                win32job.AssignProcessToJobObject(self.job, handle)
            finally:
                handle.Close()
            process.stdin.write(b"1")
            process.stdin.close()
            return process
        except BaseException:
            process.stdin.close()
            process.kill()
            process.wait(timeout=5)
            raise

    def close(self) -> dict:
        result = {"name": self.item["name"], "graceful": False}
        try:
            if (
                self.process is not None
                and self.process.poll() is None
                and self.item.get("stop_command")
            ):
                hook = self.spawn(self.item["stop_command"])
                timeout = self.item.get("stop_timeout", 15)
                deadline = time.monotonic() + timeout
                hook.wait(timeout=timeout)
                self.process.wait(timeout=max(0.1, deadline - time.monotonic()))
                result["graceful"] = (
                    hook.returncode == 0 and self.process.returncode == 0
                )
        except (OSError, subprocess.TimeoutExpired):
            result["graceful"] = False
        finally:
            # Handle ownership, not a PID from a file, determines what is stopped.
            win32job.TerminateJobObject(self.job, 137)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                accounting = win32job.QueryInformationJobObject(
                    self.job, win32job.JobObjectBasicAccountingInformation
                )
                if accounting["ActiveProcesses"] == 0:
                    break
                time.sleep(0.05)
            result["stopped"] = accounting["ActiveProcesses"] == 0
            self.job.Close()
            if self.process is not None:
                self.process.wait(timeout=5)
            self.log.close()
        return result


def reserve_ports(manifest: dict) -> dict:
    reservations = {}
    try:
        for item in manifest["services"]:
            if "port" not in item:
                continue
            sock = socket.socket()
            reservations[item["name"]] = sock
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(("127.0.0.1", item["port"]))
            except OSError as exc:
                raise RuntimeErrorState(f"port already in use: {item['name']}") from exc
        return reservations
    except BaseException:
        for sock in reservations.values():
            sock.close()
        raise


def run_runtime(
    path: Path, manifest: dict, wait_seconds: float, host_closed=None
) -> int:
    state = state_path(path, manifest)
    with owned_mutex(state):
        event = win32event.CreateEvent(None, True, False, object_name(state) + "-stop")
        win32event.ResetEvent(event)
        services = []
        reservations = {}
        snapshot = {"version": 2, "phase": "starting", "services": []}
        failure = None

        def checkpoint():
            if host_closed is not None and host_closed.is_set():
                raise StopRequested()
            if win32event.WaitForSingleObject(event, 0) == win32event.WAIT_OBJECT_0:
                raise StopRequested()
            for service in services:
                if (
                    service.item.get("mode") != "oneshot"
                    and service.process
                    and service.process.poll() is not None
                ):
                    raise RuntimeErrorState(f"service exited: {service.item['name']}")

        try:
            reservations = reserve_ports(manifest)
            write_json(state, snapshot)
            for item in manifest["services"]:
                checkpoint()
                service = OwnedService(item, path.parent)
                services.append(service)
                if item["name"] in reservations:
                    reservations.pop(item["name"]).close()
                service.process = service.spawn(item["command"])
                snapshot["services"].append(
                    {"name": item["name"], "pid": service.process.pid}
                )
                write_json(state, snapshot)
                deadline = time.monotonic() + item.get("timeout", wait_seconds)
                probe = None
                while True:
                    checkpoint()
                    if item.get("mode") == "oneshot":
                        code = service.process.poll()
                        if code is not None:
                            if code:
                                raise RuntimeErrorState(
                                    f"setup command failed: {item['name']}"
                                )
                            break
                    elif item.get("ready_command"):
                        if probe is None:
                            probe = service.spawn(item["ready_command"])
                        if probe.poll() == 0:
                            break
                        if probe.poll() is not None:
                            probe = None
                    elif item.get("health_url"):
                        if health_ok(item["health_url"]):
                            break
                    else:
                        # Liveness only; services needing readiness supply an explicit probe.
                        if (
                            time.monotonic()
                            >= deadline - item.get("timeout", wait_seconds) + 0.3
                        ):
                            break
                    if time.monotonic() >= deadline:
                        raise RuntimeErrorState(
                            f"service readiness timeout: {item['name']}"
                        )
                    time.sleep(0.1)
            checkpoint()
            snapshot["phase"] = "running"
            write_json(state, snapshot)
            print(
                json.dumps(
                    {"phase": "running", "services": [s.item["name"] for s in services]}
                ),
                flush=True,
            )
            while True:
                checkpoint()
                time.sleep(0.1)
        except (StopRequested, KeyboardInterrupt):
            pass
        except Exception as exc:
            failure = (
                str(exc) if isinstance(exc, RuntimeErrorState) else type(exc).__name__
            )
        finally:
            snapshot["phase"] = "stopping"
            try:
                write_json(state, snapshot)
            finally:
                cleanup = []
                for service in reversed(services):
                    try:
                        result = service.close()
                        cleanup.append(result)
                        if not result["stopped"]:
                            failure = failure or "service cleanup deadline exceeded"
                    except Exception as exc:
                        cleanup.append(
                            {
                                "name": service.item["name"],
                                "stopped": False,
                                "error": type(exc).__name__,
                            }
                        )
                        failure = failure or "service cleanup failed"
                for sock in reservations.values():
                    sock.close()
                event.Close()
            snapshot.update(phase="failed" if failure else "stopped", cleanup=cleanup)
            if failure:
                snapshot["error"] = failure
            write_json(state, snapshot)
        if failure:
            raise RuntimeErrorState(failure)
        return 0


def stop_runtime(state: Path, timeout: float) -> int:
    # Mutex ownership is authoritative; stale state never targets another PID.
    if not controller_active(state):
        return 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            handle = win32event.OpenEvent(
                win32con.EVENT_MODIFY_STATE, False, object_name(state) + "-stop"
            )
        except OSError:
            if not controller_active(state):
                return 0
            time.sleep(0.1)
            continue
        try:
            win32event.SetEvent(handle)
        finally:
            handle.Close()
        while time.monotonic() < deadline:
            if not controller_active(state):
                return 0
            time.sleep(0.1)
        break
    raise RuntimeErrorState(
        "stop timeout; controller still owns services; inspect state and retry"
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_child":
        if sys.stdin.buffer.read(1) != b"1":
            return 2
        return subprocess.call(
            sys.argv[2:],
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    parser = argparse.ArgumentParser(
        description="Manage the unpackaged Windows desktop runtime"
    )
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--manifest", default="desktop-runtime.json")
    parser.add_argument("--wait-seconds", type=float, default=30)
    parser.add_argument(
        "--host-stdin",
        action="store_true",
        help="stop when the owning host pipe closes",
    )
    args = parser.parse_args()
    try:
        if os.name != "nt":
            raise RuntimeErrorState("this desktop controller requires Windows")
        if not 0 < args.wait_seconds <= 300:
            raise RuntimeErrorState("wait-seconds must be between 0 and 300")
        path = Path(args.manifest).resolve()
        manifest = read_manifest(path)
        state = state_path(path, manifest)
        if args.action == "start":
            host_closed = None
            if args.host_stdin:
                host_closed = threading.Event()

                def watch_host():
                    while sys.stdin.buffer.read(1):
                        pass
                    host_closed.set()

                threading.Thread(target=watch_host, daemon=True).start()
            return run_runtime(path, manifest, args.wait_seconds, host_closed)
        if args.action == "stop":
            return stop_runtime(state, args.wait_seconds)
        active = controller_active(state)
        snapshot = (
            json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
        )
        print(
            json.dumps(
                {
                    "active": active,
                    "phase": snapshot.get("phase", "starting") if active else "stopped",
                    "last_run": snapshot,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (RuntimeErrorState, OSError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, RuntimeErrorState) else type(exc).__name__
        print(f"desktop runtime: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
