import pytest

from infrastructure.config.settings import ApiSettings, WorkerSettings

_API = {
    "DATABASE_URL": "postgresql://u:p@host:5432/db",
    "JWKS_URL": "http://identity:8000/internal/v1/jwks",
    "LEAD_CORE_URL": "http://lead-core:8000",
    "SERVICE_CLIENT_SECRET": "s3cret",
}
_WORKER = {
    "DATABASE_URL": _API["DATABASE_URL"],
    "LEAD_CORE_URL": _API["LEAD_CORE_URL"],
    "SERVICE_CLIENT_SECRET": _API["SERVICE_CLIENT_SECRET"],
    "RABBITMQ_URL": "amqp://guest:guest@rabbit:5672/",
    "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
}
_ALL = {*_API, *_WORKER, "IDENTITY_URL", "SERVICE_CLIENT_ID", "LOG_LEVEL", "OUTBOX_RELAY_INTERVAL_SECONDS"}


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

    assert (settings.database_url, settings.jwks_url, settings.lead_core_url) == (
        _API["DATABASE_URL"], _API["JWKS_URL"], _API["LEAD_CORE_URL"])
    assert (settings.identity_url, settings.service_client_id, settings.log_level) == (
        "http://identity:8000", "intake", "INFO")


@pytest.mark.parametrize("name", sorted(_API))
def test_the_api_requires_each_of_its_variables(environment, name):
    _set(environment, _API)
    environment.delenv(name)

    with pytest.raises(ValueError, match=name):
        ApiSettings.from_environment()


def test_the_worker_needs_no_jwks_and_the_api_needs_no_broker(environment):
    _set(environment, _WORKER)
    assert WorkerSettings.from_environment().outbox_relay_interval_seconds == 1.0

    for name in ("RABBITMQ_URL", "KAFKA_BOOTSTRAP_SERVERS"):
        environment.delenv(name)
    _set(environment, {"JWKS_URL": _API["JWKS_URL"]})
    assert ApiSettings.from_environment().jwks_url == _API["JWKS_URL"]


@pytest.mark.parametrize("name", sorted(_WORKER))
def test_the_worker_requires_each_of_its_variables(environment, name):
    _set(environment, _WORKER)
    environment.delenv(name)

    with pytest.raises(ValueError, match=name):
        WorkerSettings.from_environment()


def test_secrets_stay_out_of_repr(environment):
    _set(environment, _WORKER)

    assert "s3cret" not in repr(WorkerSettings.from_environment())
    assert "guest" not in repr(WorkerSettings.from_environment())
    _set(environment, {"JWKS_URL": _API["JWKS_URL"]})
    assert "s3cret" not in repr(ApiSettings.from_environment())
