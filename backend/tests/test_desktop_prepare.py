"""Installed first-launch regressions; never read or alter the user's profile."""

import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows desktop runtime")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/desktop_prepare.py"
spec = importlib.util.spec_from_file_location("desktop_prepare_tests", SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.fixture
def layout(tmp_path):
    payload = tmp_path / "中文 安装目录" / "edunova"
    data = tmp_path / "中文 用户数据"
    for relative in prepare.REQUIRED:
        filename = payload / relative
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text("fixture", encoding="utf-8")
    return payload, data


def test_restart_preserves_keys_database_and_browser_origin(layout):
    payload, data = layout
    filename = prepare.prepare(payload, data)
    settings = (data / "installation.json").read_bytes()
    config = filename.read_bytes()
    database = data / "postgres"
    database.mkdir()
    (database / "PG_VERSION").write_text("16", encoding="utf-8")
    (database / "preserved").write_bytes(b"user data")
    prepare.prepare(payload, data)
    assert (data / "installation.json").read_bytes() == settings
    assert filename.read_bytes() == config
    assert (database / "preserved").read_bytes() == b"user data"
    assert not settings.startswith(b"\xef\xbb\xbf")
    assert "中文" in filename.read_text(encoding="utf-8")


def test_missing_or_corrupted_credentials_do_not_replace_database(layout):
    payload, data = layout
    database = data / "postgres"
    database.mkdir(parents=True)
    marker = database / "preserved"
    marker.write_bytes(b"user data")
    with pytest.raises(ValueError, match="缺少凭据"):
        prepare.prepare(payload, data)
    assert not (data / "installation.json").exists()
    (data / "installation.json").write_text('{"schemaVersion": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="凭据损坏"):
        prepare.prepare(payload, data)
    assert marker.read_bytes() == b"user data"


def test_reselect_busy_port_without_changing_credentials(layout):
    payload, data = layout
    prepare.prepare(payload, data)
    original = json.loads((data / "installation.json").read_text(encoding="utf-8"))
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", original["ports"]["api"]))
        occupied.listen()
        prepare.prepare(payload, data)
    updated = json.loads((data / "installation.json").read_text(encoding="utf-8"))
    assert updated["ports"]["api"] != original["ports"]["api"]
    assert len(set(updated["ports"].values())) == len(updated["ports"])
    assert updated["encryptionKey"] == original["encryptionKey"]
    assert updated["databasePassword"] == original["databasePassword"]


def test_environment_and_paths_are_independent_of_development(layout, monkeypatch):
    payload, data = layout
    monkeypatch.setenv("SYSTEM_MODEL_API_KEY", "must-not-ship")
    monkeypatch.setenv("PYTHONPATH", "untrusted-development-path")
    monkeypatch.setenv("DATABASE_URL", "must-not-use")
    prepare.prepare(payload, data)
    manifest = json.loads((data / "runtime/services.json").read_text(encoding="utf-8"))
    assert "must-not-ship" not in json.dumps(manifest)
    assert "must-not-use" not in json.dumps(manifest)
    assert [service["name"] for service in manifest["services"]][:3] == ["initialize", "postgres", "migrations"]
    redis = next(service for service in manifest["services"] if service["name"] == "redis")
    assert redis["command"][1] == "redis.conf"
    assert 'dir "../redis"' in (data / "runtime/redis.conf").read_text(encoding="utf-8")
    for service in manifest["services"]:
        assert Path(service["command"][0]).is_relative_to(payload)
        if service["command"][0].endswith("python.exe"):
            assert "-B" in service["command"]
        assert service["env"]["SYSTEM_MODEL_API_KEY"] is None
        assert service["env"]["PYTHONPATH"] is None
        assert service["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert Path(service["cwd"]).is_relative_to(data)
    from desktop_runtime import read_manifest

    read_manifest(data / "runtime/services.json")


def test_no_preparation_over_active_controller_or_installation_directory(layout):
    payload, data = layout
    with pytest.raises(ValueError, match="分开"):
        prepare.prepare(payload, payload / "user-data")
    prepare.prepare(payload, data)
    before = (data / "installation.json").read_bytes()
    # Use another process: Windows mutex ownership is recursive per thread.
    program = (
        "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from desktop_runtime import owned_mutex; "
        "m=owned_mutex(Path(sys.argv[2])); m.__enter__(); print('locked',flush=True); input()"
    )
    import sys

    child = subprocess.Popen(
        [sys.executable, "-c", program, str(SCRIPT.parent), str(data / "runtime/state.json")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(RuntimeError, match="active"):
            prepare.prepare(payload, data)
        assert (data / "installation.json").read_bytes() == before
    finally:
        child.communicate("\n", timeout=10)


def test_failed_initialization_never_activates_partial_cluster(layout, monkeypatch):
    payload, data = layout
    prepare.prepare(payload, data)

    def failed(command, **kwargs):
        staging = Path(command[command.index("-D") + 1])
        staging.mkdir()
        (staging / "partial").write_bytes(b"interrupted initialization")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(prepare.subprocess, "run", failed)
    with pytest.raises(subprocess.CalledProcessError):
        prepare.initialize(payload, data)
    assert not (data / "postgres").exists()
    assert not (data / "runtime/initialization-password").exists()

    def succeeded(command, **kwargs):
        staging = Path(command[command.index("-D") + 1])
        staging.mkdir()
        (staging / "PG_VERSION").write_text("16", encoding="utf-8")

    monkeypatch.setattr(prepare.subprocess, "run", succeeded)
    prepare.initialize(payload, data)
    assert (data / "postgres/PG_VERSION").read_text(encoding="utf-8") == "16"
