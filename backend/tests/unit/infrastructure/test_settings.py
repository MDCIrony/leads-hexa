import pytest

from infrastructure.config.settings import Settings


def test_reads_every_value_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWKS_URL", "http://identity.test/internal/v1/jwks")
    monkeypatch.setenv("WEBHOOK_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.test:9092")

    settings = Settings.from_environment()

    assert settings.database_url == "postgresql://u:p@host:5432/db"
    assert settings.jwks_url == "http://identity.test/internal/v1/jwks"
    assert settings.webhook_timeout_seconds == 2.5
    assert settings.kafka_bootstrap_servers == "kafka.test:9092"


def test_missing_database_url_fails_loudly(monkeypatch):
    """A silent fallback is what once let this app write to an unrelated
    in-memory database while a real PostgreSQL container sat empty next to it."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_environment()


def test_missing_jwks_url_fails_loudly(monkeypatch):
    """Without it no bearer verifies, so every request would be a 401 or a 503."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("JWKS_URL", raising=False)

    with pytest.raises(ValueError, match="JWKS_URL"):
        Settings.from_environment()


def test_identity_settings_default_to_the_compose_names(monkeypatch):
    for name in ("IDENTITY_URL", "SERVICE_CLIENT_ID", "SERVICE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_environment()

    assert (settings.identity_url, settings.service_client_id) == ("http://identity:8000", "lead-core")
    # Not required here: the worker builds the same Settings and never calls identity.
    assert settings.service_client_secret == ""


def test_the_api_refuses_to_start_without_a_service_secret(monkeypatch):
    import asyncio

    from infrastructure.main import app, lifespan

    monkeypatch.setenv("SERVICE_CLIENT_SECRET", "")

    async def start() -> None:
        async with lifespan(app):
            pass

    with pytest.raises(ValueError, match="SERVICE_CLIENT_SECRET"):
        asyncio.run(start())
