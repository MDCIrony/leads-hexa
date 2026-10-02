import pytest

from infrastructure.config.settings import ApiSettings


def test_reads_the_database_url_and_defaults_the_log_level(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert ApiSettings.from_environment() == ApiSettings("postgresql://u:p@host:5432/db", "INFO")


def test_reads_the_log_level(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert ApiSettings.from_environment().log_level == "DEBUG"


def test_a_missing_database_url_is_named_in_the_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        ApiSettings.from_environment()
