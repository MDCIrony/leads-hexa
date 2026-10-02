import pytest

from infrastructure.config.settings import Settings

_REQUIRED = {
    "DATABASE_URL": "postgresql://u:p@host:5432/db",
    "JWKS_URL": "http://identity.test/jwks",
    "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
}


def test_reads_every_variable_and_defaults_the_log_level(monkeypatch):
    for name, value in _REQUIRED.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings.from_environment()

    assert settings == Settings("postgresql://u:p@host:5432/db", "http://identity.test/jwks", "kafka:9092", "INFO")


@pytest.mark.parametrize("missing", sorted(_REQUIRED))
def test_a_missing_variable_is_named_in_the_error(monkeypatch, missing):
    for name, value in _REQUIRED.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing)

    with pytest.raises(ValueError, match=missing):
        Settings.from_environment()
