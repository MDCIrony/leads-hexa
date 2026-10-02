"""One settings class per process: each requires only the variables it uses, so the
API never needs a reachable broker and the worker never needs the JWKS."""
import os
from dataclasses import dataclass, field
from typing import Self


def _required(name: str) -> str:
    # No fallback: a silent default is what once let a service write to an
    # unrelated database while the real one sat empty next to it.
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required and has no default")
    return value


@dataclass(frozen=True)
class ApiSettings:
    database_url: str = field(repr=False)
    # Where identity publishes the keys that sign the gateway's internal bearer.
    jwks_url: str
    # Out of repr, so logging the settings never prints it.
    service_client_secret: str = field(repr=False)
    identity_url: str = "http://identity:8000"
    service_client_id: str = "lead-core"
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            jwks_url=_required("JWKS_URL"),
            service_client_secret=_required("SERVICE_CLIENT_SECRET"),
            identity_url=os.getenv("IDENTITY_URL", "http://identity:8000"),
            service_client_id=os.getenv("SERVICE_CLIENT_ID", "lead-core"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str = field(repr=False)
    # Required like in identity and intake, though the worker starts with no live
    # broker (ADR-0026): the relay retries once one is reachable.
    kafka_bootstrap_servers: str
    webhook_timeout_seconds: float = 5.0
    outbox_relay_interval_seconds: float = 1.0
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            kafka_bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
