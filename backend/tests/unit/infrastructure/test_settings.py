import pytest

from infrastructure.config.settings import Settings


def test_reads_every_value_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")

    settings = Settings.from_environment()

    assert settings.database_url == "postgresql://u:p@host:5432/db"
    assert settings.jwt_secret == "a-secret"
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_missing_database_url_fails_loudly(monkeypatch):
    """A silent fallback is what once let this app write to an unrelated
    in-memory database while a real PostgreSQL container sat empty next to it."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "a-secret")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_environment()


def test_missing_jwt_secret_fails_loudly(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings.from_environment()


def test_cors_origins_default_covers_the_bare_localhost_origin(monkeypatch):
    """A browser serving the SPA on port 80 sends `http://localhost` with no
    port, so the default must include it or the preflight fails."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert "http://localhost" in Settings.from_environment().cors_origins


def test_whitespace_around_origins_is_trimmed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.setenv("CORS_ORIGINS", " http://a.test , http://b.test ")

    assert Settings.from_environment().cors_origins == ["http://a.test", "http://b.test"]
