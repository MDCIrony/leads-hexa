import pytest

from infrastructure.config.settings import Settings


def test_reads_every_value_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("SESSION_HOURS", "12")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://a.test")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://a.test/oauth/google")

    settings = Settings.from_environment()

    assert settings.database_url == "postgresql://u:p@host:5432/db"
    assert settings.session_hours == 12
    assert settings.session_cookie_secure is True
    assert settings.mfa_encryption_key == "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.frontend_origin == "http://a.test"
    assert settings.google_oauth.enabled is True


def test_missing_database_url_fails_loudly(monkeypatch):
    """A silent fallback is what once let this app write to an unrelated
    in-memory database while a real PostgreSQL container sat empty next to it."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_environment()


def test_missing_mfa_key_fails_loudly(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("MFA_ENCRYPTION_KEY", raising=False)

    with pytest.raises(ValueError, match="MFA_ENCRYPTION_KEY"):
        Settings.from_environment()


def test_cors_origins_default_covers_the_bare_localhost_origin(monkeypatch):
    """A browser serving the SPA on port 80 sends `http://localhost` with no
    port, so the default must include it or the preflight fails."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert "http://localhost" in Settings.from_environment().cors_origins


def test_session_defaults_are_eight_hours_without_secure_flag(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("SESSION_HOURS", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)

    settings = Settings.from_environment()

    assert settings.session_hours == 8
    assert settings.session_cookie_secure is False


def test_whitespace_around_origins_is_trimmed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("CORS_ORIGINS", " http://a.test , http://b.test ")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://a.test")

    assert Settings.from_environment().cors_origins == ["http://a.test", "http://b.test"]


def test_frontend_origin_must_be_an_allowed_origin_and_partial_oauth_is_disabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://other.test/login")
    with pytest.raises(ValueError, match="FRONTEND_ORIGIN"):
        Settings.from_environment()

    monkeypatch.setenv("FRONTEND_ORIGIN", "http://a.test")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "configured-alone")
    assert Settings.from_environment().google_oauth.enabled is False


def test_oauth_test_mode_requires_an_explicit_test_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("OAUTH_TEST_MODE", "true")
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(ValueError, match="APP_ENV=test"):
        Settings.from_environment()

    monkeypatch.setenv("APP_ENV", "test")
    settings = Settings.from_environment()
    assert settings.oauth_test_mode is True
    assert settings.google_oauth.enabled is True


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
