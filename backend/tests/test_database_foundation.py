from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from backend.app.core.config import Settings, get_settings
from backend.app.db.base import Base
from backend.app.db.session import build_engine


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_read_database_and_redis_urls_from_environment(monkeypatch) -> None:
    database_url = "postgresql+psycopg://tester:test_password@localhost:5432/edunova_test"
    redis_url = "redis://localhost:6380/2"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == database_url
    assert settings.redis_url == redis_url


def test_settings_have_development_database_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == (
        "postgresql+psycopg://edunova:edunova_dev_password@localhost:5432/edunova"
    )
    assert settings.redis_url == "redis://localhost:6379/0"


def test_build_engine_uses_configured_database_url() -> None:
    database_url = "postgresql+psycopg://tester:test_password@localhost:5432/edunova_test"

    engine = build_engine(database_url)

    try:
        assert isinstance(engine, Engine)
        assert engine.url.render_as_string(hide_password=False) == database_url
    finally:
        engine.dispose()


def test_application_metadata_is_available_for_alembic() -> None:
    assert Base.metadata is not None
    assert hasattr(Base.metadata, "tables")

    env_text = (REPO_ROOT / "backend" / "migrations" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "target_metadata = Base.metadata" in env_text


def test_initial_migration_enables_pgvector_extension() -> None:
    versions_dir = REPO_ROOT / "backend" / "migrations" / "versions"
    migration_text = "\n".join(
        path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py")
    )

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_text
    assert "DROP EXTENSION IF EXISTS vector" in migration_text
