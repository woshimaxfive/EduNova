"""Windows process-boundary regressions, using only owned temporary services."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows desktop lifecycle")
CONTROLLER = Path(__file__).resolve().parents[2] / "scripts/desktop_runtime.py"


def wait_for(check, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition was not met before deadline")


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path / "中文 空格 数据"
    root.mkdir()
    server = root / "service.py"
    server.write_text(
        """import os,sys,time,json,subprocess,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(180)'],creationflags=subprocess.CREATE_NO_WINDOW)
Path('pids.json').write_text(json.dumps([os.getpid(),child.pid]),encoding='utf-8')
def crash():
    while not Path('crash').exists(): time.sleep(.05)
    os._exit(7)
threading.Thread(target=crash,daemon=True).start()
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'ok')
    def log_message(self,*args): pass
ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()
""",
        encoding="utf-8",
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    manifest = root / "manifest.json"
    service = {
        "name": "http",
        "command": [sys.executable, str(server), str(port)],
        "health_url": f"http://127.0.0.1:{port}/health",
    }
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    children = []

    def call(action, background=False, wait=12):
        args = [
            sys.executable,
            str(CONTROLLER),
            action,
            "--manifest",
            str(manifest),
            "--wait-seconds",
            str(wait),
        ]
        if background:
            p = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            children.append(p)
            return p
        return subprocess.run(
            args,
            capture_output=True,
            timeout=wait + 8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def state():
        try:
            return json.loads((root / "state.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    yield root, manifest, service, port, call, state
    call("stop")
    for child in children:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)


def assert_ports_released(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))


def process_handles(root):
    import win32api
    import win32con

    return [
        win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid)
        for pid in json.loads((root / "pids.json").read_text(encoding="utf-8"))
    ]


def assert_handles_exited(handles):
    import win32event

    try:
        for handle in handles:
            assert (
                win32event.WaitForSingleObject(handle, 8000) == win32event.WAIT_OBJECT_0
            )
    finally:
        for handle in handles:
            handle.Close()


def test_start_stop_chinese_path_and_descendants(runtime):
    root, _, _, port, call, state = runtime
    process = call("start", True)
    wait_for(lambda: state().get("phase") == "running")
    handles = process_handles(root)
    assert json.loads(call("status").stdout)["active"] is True
    assert call("stop").returncode == 0
    assert process.wait(timeout=10) == 0
    assert_handles_exited(handles)
    assert_ports_released(port)
    assert state()["cleanup"][0]["stopped"] is True
    assert call("stop").returncode == 0


def test_simultaneous_start_has_one_owner(runtime):
    _, _, _, _, call, state = runtime
    first, second = call("start", True), call("start", True)
    wait_for(lambda: first.poll() is not None or second.poll() is not None)
    loser = first if first.poll() is not None else second
    assert loser.returncode == 2
    wait_for(lambda: state().get("phase") == "running")
    assert call("stop").returncode == 0


def test_foreign_port_conflict_does_not_touch_listener(runtime):
    root, _, _, port, call, state = runtime
    with socket.socket() as foreign:
        foreign.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        foreign.bind(("127.0.0.1", port))
        foreign.listen()
        result = call("start")
        assert result.returncode == 2
        assert b"port already in use" in result.stderr
        assert foreign.getsockname()[1] == port
        assert not (root / "pids.json").exists()
        assert state()["phase"] == "failed"


def test_partial_start_failure_rolls_back(runtime):
    root, manifest, service, port, call, state = runtime
    broken = {
        "name": "broken",
        "command": [sys.executable, "-c", "raise SystemExit(9)"],
    }
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service, broken]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = call("start")
    assert result.returncode == 2
    assert state()["phase"] == "failed"
    assert all(item["stopped"] for item in state()["cleanup"])
    assert_ports_released(port)


def test_controller_crash_reaps_owned_tree(runtime):
    root, _, _, port, call, state = runtime
    process = call("start", True)
    wait_for(lambda: state().get("phase") == "running")
    handles = process_handles(root)
    process.kill()
    process.wait(timeout=10)
    assert_handles_exited(handles)
    assert_ports_released(port)
    assert json.loads(call("status").stdout)["active"] is False
    # The stale snapshot is not used to terminate any PID on restart.
    old_pids = (root / "pids.json").read_text(encoding="utf-8")
    again = call("start", True)
    wait_for(
        lambda: (
            state().get("phase") == "running"
            and (root / "pids.json").read_text(encoding="utf-8") != old_pids
        )
    )
    assert again.poll() is None


def test_service_crash_stops_remaining_tree(runtime):
    root, _, _, port, call, state = runtime
    process = call("start", True)
    wait_for(lambda: state().get("phase") == "running")
    handles = process_handles(root)
    (root / "crash").touch()
    assert process.wait(timeout=12) == 2
    assert_handles_exited(handles)
    assert_ports_released(port)
    assert state()["phase"] == "failed"


def test_stale_pid_never_controls_an_unrelated_process(runtime):
    root, _, _, _, call, _ = runtime
    (root / "state.json").write_text(
        json.dumps(
            {"services": [{"name": "foreign", "pid": os.getpid()}]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    assert call("stop").returncode == 0
    assert json.loads(call("status").stdout)["active"] is False


def test_health_timeout_rolls_back(runtime):
    _, manifest, service, port, call, state = runtime
    service["command"] = [sys.executable, "-c", "import time; time.sleep(180)"]
    service["timeout"] = 0.5
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    result = call("start")
    assert result.returncode == 2
    assert "readiness timeout" in state()["error"]
    assert state()["cleanup"][0]["stopped"]
    assert_ports_released(port)


def test_stop_during_startup_cancels_owned_services(runtime):
    _, manifest, service, port, call, state = runtime
    service["command"] = [sys.executable, "-c", "import time; time.sleep(180)"]
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    process = call("start", True)
    wait_for(lambda: len(state().get("services", [])) == 1)
    assert call("stop").returncode == 0
    assert process.wait(timeout=10) == 0
    assert state()["phase"] == "stopped"
    assert_ports_released(port)


def test_hanging_shutdown_is_bounded_and_reported(runtime):
    root, manifest, service, port, call, state = runtime
    service["stop_command"] = [sys.executable, "-c", "import time; time.sleep(180)"]
    service["stop_timeout"] = 0.3
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    process = call("start", True)
    wait_for(lambda: state().get("phase") == "running")
    handles = process_handles(root)
    assert call("stop").returncode == 0
    assert process.wait(timeout=10) == 0
    assert_handles_exited(handles)
    assert state()["cleanup"][0] == {"name": "http", "graceful": False, "stopped": True}
    assert_ports_released(port)


def test_invalid_manifest_is_rejected_before_launch(runtime):
    root, manifest, service, _, call, _ = runtime
    invalid = {"name": "invalid", "command": ["relative.exe"]}
    manifest.write_text(
        json.dumps(
            {"state_file": "state.json", "services": [service, invalid]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = call("start")
    assert result.returncode == 2
    assert b"absolute executable" in result.stderr
    assert not (root / "pids.json").exists()
