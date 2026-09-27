import json
from pathlib import Path
import subprocess
import sys


BRIDGE = Path(__file__).resolve().parents[2] / "scripts/desktop_host_bridge.py"


def test_bridge_rejects_unknown_fields_before_controller(tmp_path):
    manifest = tmp_path / "runtime.json"
    manifest.write_text(
        json.dumps({"services": [{"name": "x", "command": [sys.executable]}]}),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(BRIDGE), "--manifest", str(manifest)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    output, _ = process.communicate(
        '{"id":"a","method":"status","command":["whoami"]}\n', timeout=5
    )
    assert json.loads(output) == {
        "id": "a",
        "ok": False,
        "error": "request must contain only id and method",
    }


def test_bridge_restricts_lifecycle_methods(tmp_path):
    manifest = tmp_path / "runtime.json"
    manifest.write_text(
        json.dumps({"services": [{"name": "x", "command": [sys.executable]}]}),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(BRIDGE), "--manifest", str(manifest)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    output, _ = process.communicate('{"id":2,"method":"exec"}\n', timeout=5)
    assert json.loads(output) == {
        "id": 2,
        "ok": False,
        "error": "unsupported lifecycle method",
    }


# Reuse the controller's real HTTP/descendant fixture; no mocked controller.
from backend.tests.test_desktop_runtime import (  # noqa: E402
    runtime,  # noqa: F401
    process_handles,
    assert_handles_exited,
    assert_ports_released,
)
import os  # noqa: E402
import pytest  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402


@pytest.mark.skipif(os.name != "nt", reason="Windows host lifecycle")
@pytest.mark.parametrize("ending", ["stop", "eof", "crash"])
def test_bridge_real_lifecycle_and_host_disconnect(runtime, ending):  # noqa: F811
    root, manifest, _, port, _, _ = runtime
    process = subprocess.Popen(
        [
            sys.executable,
            str(BRIDGE),
            "--manifest",
            str(manifest),
            "--wait-seconds",
            "8",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    pool = ThreadPoolExecutor(max_workers=1)

    def rpc(value):
        process.stdin.write(value + "\n")
        process.stdin.flush()
        return json.loads(pool.submit(process.stdout.readline).result(timeout=15))

    try:
        assert rpc('{"id":1,"method":"start"}')["result"]["phase"] == "running"
        handles = process_handles(root)
        assert rpc('{"id":2,"method":"start"}')["result"]["already_owned"]
        status = rpc('{"id":3,"method":"status"}')["result"]
        assert status == {"active": True, "phase": "running", "owned": True}
        assert rpc("{broken")["id"] is None
        assert rpc('{"id":4,"method":"exec"}')["ok"] is False
        if ending == "stop":
            assert rpc('{"id":5,"method":"stop"}')["ok"]
            assert rpc('{"id":6,"method":"status"}')["result"]["active"] is False
        elif ending == "crash":
            process.kill()
        if not process.stdin.closed:
            process.stdin.close()
        process.wait(timeout=15)
        assert_handles_exited(handles)
        assert_ports_released(port)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=15)
        pool.shutdown(wait=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows host lifecycle")
def test_bridge_does_not_stop_foreign_owner(runtime):  # noqa: F811
    _, manifest, _, _, call, state = runtime
    from backend.tests.test_desktop_runtime import wait_for

    owner = call("start", True)
    wait_for(lambda: state().get("phase") == "running")
    result = subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "--manifest",
            str(manifest),
            "--wait-seconds",
            "4",
        ],
        input='{"id":1,"method":"start"}\n{"id":2,"method":"stop"}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    assert messages[0]["ok"] is False
    assert messages[1]["ok"] is True
    assert owner.poll() is None
    assert json.loads(call("status").stdout)["active"]
