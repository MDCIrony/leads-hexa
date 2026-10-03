import pytest

from infrastructure.config.settings import ApiSettings, WorkerSettings

_API = {
    "DATABASE_URL": "postgresql://u:p@host:5432/db",
    "JWKS_URL": "http://identity:8000/internal/v1/jwks",
    "SERVICE_CLIENT_SECRET": "s3cret",
}
_WORKER = {
    "DATABASE_URL": _API["DATABASE_URL"],
    "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
}
_ALL = {*_API, *_WORKER, "IDENTITY_URL", "SERVICE_CLIENT_ID", "LOG_LEVEL", "WEBHOOK_TIMEOUT_SECONDS",
        "OUTBOX_RELAY_INTERVAL_SECONDS"}


@pytest.fixture
def environment(monkeypatch):
    """Starts from an empty environment: conftest's suite-wide values would hide a missing variable."""
    for name in _ALL:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _set(monkeypatch, values):
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_the_api_reads_its_variables_and_defaults_the_rest(environment):
    _set(environment, _API)

    settings = ApiSettings.from_environment()

    assert (settings.database_url, settings.jwks_url, settings.service_client_secret) == (
        _API["DATABASE_URL"], _API["JWKS_URL"], _API["SERVICE_CLIENT_SECRET"])
    assert (settings.identity_url, settings.service_client_id, settings.log_level) == (
        "http://identity:8000", "lead-core", "INFO")


@pytest.mark.parametrize("name", sorted(_API))
def test_the_api_requires_each_of_its_variables(environment, name):
    """Without the database nothing is stored, without the JWKS no bearer verifies, and without
    the secret the first assignment would fail with a 503 instead of the start."""
    _set(environment, _API)
    environment.delenv(name)

    with pytest.raises(ValueError, match=name):
        ApiSettings.from_environment()


def test_the_worker_reads_its_variables_and_defaults_the_rest(environment):
    _set(environment, _WORKER)

    settings = WorkerSettings.from_environment()

    assert (settings.database_url, settings.kafka_bootstrap_servers) == (
        _WORKER["DATABASE_URL"], _WORKER["KAFKA_BOOTSTRAP_SERVERS"])
    assert (settings.webhook_timeout_seconds, settings.outbox_relay_interval_seconds, settings.log_level) == (
        5.0, 1.0, "INFO")


@pytest.mark.parametrize("name", sorted(_WORKER))
def test_the_worker_requires_each_of_its_variables(environment, name):
    _set(environment, _WORKER)
    environment.delenv(name)

    with pytest.raises(ValueError, match=name):
        WorkerSettings.from_environment()


def test_each_process_needs_only_its_own_variables(environment):
    _set(environment, _WORKER)
    assert WorkerSettings.from_environment().kafka_bootstrap_servers == "kafka:9092"

    environment.delenv("KAFKA_BOOTSTRAP_SERVERS")
    _set(environment, {"JWKS_URL": _API["JWKS_URL"], "SERVICE_CLIENT_SECRET": "s3cret"})
    assert ApiSettings.from_environment().jwks_url == _API["JWKS_URL"]


def test_the_dsn_and_the_secret_stay_out_of_repr(environment):
    _set(environment, _API | _WORKER)

    for text in (repr(ApiSettings.from_environment()), repr(WorkerSettings.from_environment())):
        assert "postgresql://" not in text
        assert "s3cret" not in text
