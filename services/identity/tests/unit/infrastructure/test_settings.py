import hashlib

import pytest

from infrastructure.config.settings import ApiSettings, WorkerSettings

_DIGEST = hashlib.sha256(b"unit-secret").hexdigest()

# Only the API's variables; anything the worker would need is deliberately absent.
_API_ENVIRONMENT = {
    "DATABASE_URL": "postgresql://u:p@host:5432/db",
    "SIGNING_KEYS": "unit-1=We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk",
    "SERVICE_CLIENTS": f"lead-core:identity:{_DIGEST}",
    "MFA_ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
}

_OPTIONAL = [
    "CORS_ORIGINS", "FRONTEND_ORIGIN", "OAUTH_TEST_MODE", "APP_ENV", "SESSION_HOURS",
    "SESSION_COOKIE_SECURE", "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_EXTERNAL_BOOTSTRAP_SERVERS",
    "LOG_LEVEL", "OUTBOX_RELAY_INTERVAL_SECONDS",
    *(f"{p}_{s}" for p in ("GOOGLE", "GITHUB") for s in ("CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI")),
]


@pytest.fixture
def api_env(monkeypatch):
    for name in _OPTIONAL:
        monkeypatch.delenv(name, raising=False)
    for name, value in _API_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_reads_every_value_from_the_environment(api_env):
    api_env.setenv("SESSION_HOURS", "12")
    api_env.setenv("SESSION_COOKIE_SECURE", "true")
    api_env.setenv("CORS_ORIGINS", "http://a.test,http://b.test")
    api_env.setenv("FRONTEND_ORIGIN", "http://a.test")
    api_env.setenv("GOOGLE_CLIENT_ID", "google-id")
    api_env.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    api_env.setenv("GOOGLE_REDIRECT_URI", "https://a.test/oauth/google")
    api_env.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    api_env.setenv("LOG_LEVEL", "DEBUG")

    settings = ApiSettings.from_environment()

    assert settings.database_url == "postgresql://u:p@host:5432/db"
    assert settings.signing_keys == _API_ENVIRONMENT["SIGNING_KEYS"]
    assert settings.mfa_encryption_key == _API_ENVIRONMENT["MFA_ENCRYPTION_KEY"]
    assert [(c.client_id, c.audiences) for c in settings.service_clients] == [("lead-core", {"identity"})]
    assert settings.session_hours == 12
    assert settings.session_cookie_secure is True
    assert settings.cors_origins == ("http://a.test", "http://b.test")
    assert settings.frontend_origin == "http://a.test"
    assert settings.google_oauth.enabled is True
    assert settings.kafka_bootstrap_servers == "kafka:9092"
    assert settings.log_level == "DEBUG"


def test_the_api_defaults(api_env):
    settings = ApiSettings.from_environment()

    assert settings.session_hours == 8
    assert settings.session_cookie_secure is False
    assert "http://localhost" in settings.cors_origins
    assert settings.frontend_origin == "http://localhost"
    # Defaulted, never required: the API must start with no broker reachable.
    assert settings.kafka_bootstrap_servers == "localhost:9092"
    assert settings.kafka_external_bootstrap_servers == "localhost:9094"
    assert settings.log_level == "INFO"
    assert not settings.google_oauth.enabled and not settings.github_oauth.enabled


@pytest.mark.parametrize("name", list(_API_ENVIRONMENT))
def test_each_required_api_variable_fails_loudly_when_missing(api_env, name):
    api_env.delenv(name)

    with pytest.raises(ValueError, match=name):
        ApiSettings.from_environment()


@pytest.mark.parametrize("value", ["", "lead-core:identity", f"lead-core:identity:{_DIGEST[:40]}"])
def test_an_empty_or_malformed_service_clients_fails_without_echoing_the_hash(api_env, value):
    api_env.setenv("SERVICE_CLIENTS", value or " , ")

    with pytest.raises(ValueError, match="SERVICE_CLIENTS") as raised:
        ApiSettings.from_environment()

    assert _DIGEST[:16] not in str(raised.value)


def test_whitespace_around_origins_is_trimmed(api_env):
    api_env.setenv("CORS_ORIGINS", " http://a.test , http://b.test ")
    api_env.setenv("FRONTEND_ORIGIN", "http://a.test")

    assert ApiSettings.from_environment().cors_origins == ("http://a.test", "http://b.test")


def test_frontend_origin_must_be_an_allowed_origin_and_partial_oauth_is_disabled(api_env):
    api_env.setenv("CORS_ORIGINS", "http://a.test")
    api_env.setenv("FRONTEND_ORIGIN", "http://other.test/login")
    with pytest.raises(ValueError, match="FRONTEND_ORIGIN"):
        ApiSettings.from_environment()

    api_env.setenv("FRONTEND_ORIGIN", "http://a.test")
    api_env.setenv("GOOGLE_CLIENT_ID", "configured-alone")
    assert ApiSettings.from_environment().google_oauth.enabled is False


def test_oauth_test_mode_requires_an_explicit_test_environment(api_env):
    api_env.setenv("OAUTH_TEST_MODE", "true")

    with pytest.raises(ValueError, match="APP_ENV=test"):
        ApiSettings.from_environment()

    api_env.setenv("APP_ENV", "test")
    settings = ApiSettings.from_environment()
    assert settings.oauth_test_mode is True
    assert settings.google_oauth.enabled is True


def test_the_worker_needs_only_its_own_variables(monkeypatch):
    for name in [*_API_ENVIRONMENT, *_OPTIONAL]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

    assert WorkerSettings.from_environment() == WorkerSettings("postgresql://u:p@host:5432/db", "kafka:9092", 1.0, "INFO")

    monkeypatch.setenv("OUTBOX_RELAY_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = WorkerSettings.from_environment()
    assert (settings.outbox_relay_interval_seconds, settings.log_level) == (0.5, "DEBUG")


@pytest.mark.parametrize("name", ["DATABASE_URL", "KAFKA_BOOTSTRAP_SERVERS"])
def test_each_required_worker_variable_fails_loudly_when_missing(monkeypatch, name):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    monkeypatch.delenv(name)

    with pytest.raises(ValueError, match=name):
        WorkerSettings.from_environment()


def test_the_settings_repr_carries_no_secret(api_env):
    api_env.setenv("GITHUB_CLIENT_SECRET", "github-secret")

    text = repr(ApiSettings.from_environment())

    for secret in ("We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk", _DIGEST[:16], "MDEyMzQ1Njc4", "github-secret"):
        assert secret not in text
