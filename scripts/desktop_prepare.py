"""Prepare an installed desktop runtime without reading development configuration.

Mutable data lives outside the installation. Database initialization and migrations
run as controller-owned steps, so closing the window also stops their children.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

# Embedded Python deliberately does not add the script directory to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_runtime import owned_mutex, write_json  # noqa: E402

REQUIRED = (
    "runtime/python/python.exe",
    "runtime/search-python/python.exe",
    "runtime/postgresql/bin/postgres.exe",
    "runtime/postgresql/bin/initdb.exe",
    "runtime/postgresql/bin/pg_ctl.exe",
    "runtime/postgresql/bin/pg_isready.exe",
    "runtime/redis/redis-server.exe",
    "app/frontend/index.html",
    "app/alembic.ini",
    "app/scripts/desktop_host_bridge.py",
    "app/scripts/desktop_runtime.py",
    "app/scripts/desktop_worker.py",
    "app/scripts/desktop_prepare.py",
    "app/scripts/desktop_search.py",
    "app/vendor/searxng/searx/webapp.py",
    "app/verifier/policy.mjs",
    "app/verifier/runtime/pyodide.mjs",
)
OS_ENV = {
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "USERPROFILE",
    "LOCALAPPDATA", "APPDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
}


def validate_paths(payload: Path, data: Path) -> tuple[Path, Path]:
    if not payload.is_absolute() or not data.is_absolute():
        raise ValueError("安装目录和用户数据目录必须使用绝对路径。")
    payload, data = payload.resolve(), data.resolve()
    if data == payload or data.is_relative_to(payload) or payload.is_relative_to(data):
        raise ValueError("用户数据目录必须与安装资源目录分开。")
    for relative in REQUIRED:
        if not (payload / relative).is_file():
            raise ValueError(f"安装资源缺失：{relative}")
    return payload, data


def installation_settings(data: Path) -> dict:
    filename = data / "installation.json"
    if filename.exists():
        value = json.loads(filename.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != 1:
            raise ValueError("用户数据版本无法识别，请保留数据并检查安装版本。")
        for key in ("databasePassword", "redisPassword", "jwtSecret"):
            if not re.fullmatch(r"[a-f0-9]{64}", str(value.get(key, ""))):
                raise ValueError("本地凭据损坏，请保留现有用户数据。")
        from cryptography.fernet import Fernet

        Fernet(value["encryptionKey"].encode("ascii"))
        value.setdefault("searchSecret", secrets.token_hex(32))
        return value
    if (data / "postgres").exists():
        raise ValueError("发现已有数据库但缺少凭据；为保护数据，停止重新初始化。")
    value = {
        "schemaVersion": 1,
        "databasePassword": secrets.token_hex(32),
        "redisPassword": secrets.token_hex(32),
        "jwtSecret": secrets.token_hex(32),
        "searchSecret": secrets.token_hex(32),
        "encryptionKey": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
        "ports": {},
    }
    write_json(filename, value)
    return value


def available_ports(previous: dict) -> dict:
    """Keep browser origin stable when possible; choose distinct free ports."""
    sockets = []
    ports = {}
    try:
        for name in ("postgres", "redis", "api", "speech", "search", "verifier"):
            sock = socket.socket()
            sockets.append(sock)
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            preferred = previous.get(name, 0)
            if type(preferred) is not int or not 1024 <= preferred <= 65535:
                preferred = 0
            try:
                sock.bind(("127.0.0.1", preferred))
            except OSError:
                sock.bind(("127.0.0.1", 0))
            ports[name] = sock.getsockname()[1]
        return ports
    finally:
        for sock in sockets:
            sock.close()


def service_environment(payload: Path, data: Path, settings: dict) -> dict:
    ports = settings["ports"]
    # Explicitly remove inherited provider keys and development overrides.
    env = {key: None for key in os.environ if key.upper() not in OS_ENV}
    env.update({
        "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
        "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HOME": str(data / "cache/huggingface"), "OTEL_SDK_DISABLED": "true",
        "APP_ENV": "desktop", "APP_DEBUG": "false",
        "DATABASE_URL": (
            f"postgresql+psycopg://edunova:{settings['databasePassword']}"
            f"@127.0.0.1:{ports['postgres']}/edunova"
        ),
        "REDIS_URL": f"redis://:{settings['redisPassword']}@127.0.0.1:{ports['redis']}/0",
        "JWT_SECRET": settings["jwtSecret"],
        "MODEL_SETTINGS_ENCRYPTION_KEY": settings["encryptionKey"],
        "MATERIAL_STORAGE_DIR": str(data / "materials"),
        "CHAT_ATTACHMENT_STORAGE_DIR": str(data / "attachments"),
        "EXPORT_DIR": str(data / "exports"),
        "LOCAL_EMBEDDING_MODEL_DIR": str(payload / "models/bge-small-zh-v1.5"),
        "DOCLING_ARTIFACTS_PATH": str(payload / "models/docling"),
        "LOCAL_SPEECH_MODEL_DIR": str(payload / "models/speech"),
        "LOCAL_SPEECH_URL": f"http://127.0.0.1:{ports['speech']}",
        "WEB_SEARCH_ENDPOINT": f"http://127.0.0.1:{ports['search']}/search",
        "CODE_VERIFIER_URL": f"http://127.0.0.1:{ports['verifier']}",
        "SEARXNG_SETTINGS_PATH": str(data / "runtime/search.yml"),
        "SEARXNG_DATA_PATH": str(data / "cache/search"),
        "EDUNOVA_SEARCH_PORT": str(ports["search"]),
        "EDUNOVA_DESKTOP_FRONTEND_DIR": str(payload / "app/frontend"),
    })
    return env


def runtime_manifest(payload: Path, data: Path, settings: dict) -> dict:
    python = payload / "runtime/python/python.exe"
    pg = payload / "runtime/postgresql/bin"
    helper = payload / "app/scripts/desktop_prepare.py"
    ports = settings["ports"]

    def action(name):
        return [str(python), "-B", "-X", "utf8", str(helper), name,
                "--payload", str(payload), "--data", str(data)]

    def code(source):
        return [str(python), "-B", "-X", "utf8", "-c", source]

    def api(module, port, factory=False):
        command = [str(python), "-B", "-X", "utf8", "-m", "uvicorn", module,
                   "--host", "127.0.0.1", "--port", str(port)]
        return command + (["--factory"] if factory else [])

    services = [
        {"name": "initialize", "mode": "oneshot", "command": action("initialize"), "timeout": 120},
        {
            "name": "postgres", "port": ports["postgres"],
            "command": [str(pg / "postgres.exe"), "-D", str(data / "postgres"),
                        "-h", "127.0.0.1", "-p", str(ports["postgres"])],
            "ready_command": [str(pg / "pg_isready.exe"), "-h", "127.0.0.1",
                              "-p", str(ports["postgres"]), "-U", "edunova", "-d", "postgres"],
            "stop_command": [str(pg / "pg_ctl.exe"), "-D", str(data / "postgres"),
                             "-m", "fast", "-w", "stop"],
            "stop_timeout": 20,
        },
        {"name": "migrations", "mode": "oneshot", "command": action("migrate"), "timeout": 120},
        {
            "name": "redis", "port": ports["redis"],
            # Redis resolves config arguments as POSIX paths under Cygwin.
            # A relative filename uses the controller's explicit runtime cwd.
            "command": [str(payload / "runtime/redis/redis-server.exe"), "redis.conf"],
            "ready_command": code("import os; from redis import Redis; assert Redis.from_url(os.environ['REDIS_URL']).ping()"),
            "stop_command": code("import os; from redis import Redis; Redis.from_url(os.environ['REDIS_URL']).shutdown(nosave=True)"),
        },
        {
            "name": "speech", "command": api("backend.app.speech_server:app", ports["speech"]),
            "health_url": f"http://127.0.0.1:{ports['speech']}/health", "timeout": 90,
        },
        {
            "name": "search",
            "command": [str(payload / "runtime/search-python/python.exe"), "-B", "-X", "utf8",
                        str(payload / "app/scripts/desktop_search.py")],
            "health_url": f"http://127.0.0.1:{ports['search']}/healthz",
            "timeout": 90,
        },
        {
            "name": "api", "command": api("backend.app.desktop_app:create_app", ports["api"], True),
            "health_url": f"http://127.0.0.1:{ports['api']}/api/health",
        },
        {
            "name": "worker",
            "command": [str(python), "-B", "-X", "utf8", str(payload / "app/scripts/desktop_worker.py"),
                        "worker", "edunova_ai", "edunova_exports"],
            "ready_command": code("import os; from redis import Redis; from rq import Worker; r=Redis.from_url(os.environ['REDIS_URL']); assert any(w.get_state() in ('idle','busy') for w in Worker.all(connection=r))"),
            "stop_command": code("import os; from redis import Redis; from rq import Worker; from rq.command import send_shutdown_command; r=Redis.from_url(os.environ['REDIS_URL']); [send_shutdown_command(r,w.name) for w in Worker.all(connection=r)]"),
        },
    ]
    env = service_environment(payload, data, settings)
    for service in services:
        service_env = env
        if service["name"] in {"speech", "search"}:
            allowed = {"PATH", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE", "HF_HUB_OFFLINE",
                       "TRANSFORMERS_OFFLINE", "HF_HOME", "OTEL_SDK_DISABLED",
                       "LOCAL_SPEECH_MODEL_DIR", "SEARXNG_SETTINGS_PATH", "SEARXNG_DATA_PATH",
                       "EDUNOVA_SEARCH_PORT"}
            service_env = {key: value if key in allowed else None for key, value in env.items()}
        service.update(env=service_env, cwd=str(data / "runtime"), log=f"logs/{service['name']}.log")
    return {"state_file": "state.json", "services": services}


def prepare(payload: Path, data: Path) -> Path:
    payload, data = validate_paths(payload, data)
    data.mkdir(parents=True, exist_ok=True)
    with owned_mutex(data / "runtime/state.json"):
        settings = installation_settings(data)
        settings["ports"] = available_ports(settings.get("ports", {}))
        for folder in ("runtime", "redis", "materials", "attachments", "exports", "profile", "cache"):
            (data / folder).mkdir(parents=True, exist_ok=True)
        write_json(data / "installation.json", settings)
        (data / "cache/search").mkdir(parents=True, exist_ok=True)
        (data / "runtime/search.yml").write_text(
            "use_default_settings: true\nserver:\n"
            f"  secret_key: {settings['searchSecret']}\n"
            "  limiter: false\n  image_proxy: false\n  bind_address: 127.0.0.1\n"
            "search:\n  default_lang: zh-CN\n  formats: [html, json]\n"
            "outgoing:\n  request_timeout: 5.0\n  max_request_timeout: 8.0\n",
            encoding="utf-8",
        )
        (data / "runtime/redis.conf").write_text(
            f"bind 127.0.0.1\nport {settings['ports']['redis']}\n"
            f"requirepass {settings['redisPassword']}\nprotected-mode yes\n"
            'appendonly yes\nsave ""\ndir "../redis"\n',
            encoding="utf-8",
        )
        manifest = data / "runtime/services.json"
        write_json(manifest, runtime_manifest(payload, data, settings))
        filename = data / "runtime/desktop.json"
        write_json(filename, {
            "python": str(payload / "runtime/python/python.exe"),
            "bridge": str(payload / "app/scripts/desktop_host_bridge.py"),
            "manifest": str(manifest), "userData": str(data / "profile"),
            "url": f"http://127.0.0.1:{settings['ports']['api']}/login",
            "startTimeoutSeconds": 300,
            "verifier": {"port": settings["ports"]["verifier"], "assets": str(payload / "app/verifier")},
        })
        return filename


def initialize(payload: Path, data: Path) -> None:
    target = data / "postgres"
    if target.exists():
        if not (target / "PG_VERSION").is_file():
            raise ValueError("数据库目录不完整，请保留该目录并检查启动日志。")
        (data / "runtime/initialization-password").unlink(missing_ok=True)
        return
    settings = installation_settings(data)
    # An interrupted attempt never becomes the active database directory.
    staging = data / ("postgres-initializing-" + secrets.token_hex(6))
    pwfile = data / "runtime/initialization-password"
    try:
        pwfile.write_text(settings["databasePassword"], encoding="utf-8")
        subprocess.run([
            str(payload / "runtime/postgresql/bin/initdb.exe"), "-D", str(staging),
            "-U", "edunova", "--pwfile", str(pwfile), "--encoding=UTF8",
            "--locale=C", "--auth=scram-sha-256",
        ], check=True, timeout=110, creationflags=subprocess.CREATE_NO_WINDOW)
        staging.rename(target)
    finally:
        pwfile.unlink(missing_ok=True)


def migrate(payload: Path) -> None:
    import psycopg
    from alembic import command
    from alembic.config import Config

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url.rsplit("/", 1)[0] + "/postgres", autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname = 'edunova'").fetchone():
            connection.execute("CREATE DATABASE edunova")
    config = Config(str(payload / "app/alembic.ini"))
    config.set_main_option("script_location", str(payload / "app/backend/migrations").replace("%", "%%"))
    command.upgrade(config, "head")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "initialize", "migrate"))
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    payload, data = validate_paths(args.payload, args.data)
    if args.action == "prepare":
        print(json.dumps({"config": str(prepare(payload, data))}, ensure_ascii=False))
    elif args.action == "initialize":
        initialize(payload, data)
    else:
        migrate(payload)


if __name__ == "__main__":
    main()
