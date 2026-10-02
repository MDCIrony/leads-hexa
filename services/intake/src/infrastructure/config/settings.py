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
    jwks_url: str
    lead_core_url: str
    # Out of repr, so logging the settings never prints it.
    service_client_secret: str = field(repr=False)
    identity_url: str = "http://identity:8000"
    service_client_id: str = "intake"
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            jwks_url=_required("JWKS_URL"),
            lead_core_url=_required("LEAD_CORE_URL"),
            service_client_secret=_required("SERVICE_CLIENT_SECRET"),
            identity_url=os.getenv("IDENTITY_URL", "http://identity:8000"),
            service_client_id=os.getenv("SERVICE_CLIENT_ID", "intake"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str = field(repr=False)
    lead_core_url: str
    service_client_secret: str = field(repr=False)
    rabbitmq_url: str = field(repr=False)
    kafka_bootstrap_servers: str
    identity_url: str = "http://identity:8000"
    service_client_id: str = "intake"
    outbox_relay_interval_seconds: float = 1.0
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            lead_core_url=_required("LEAD_CORE_URL"),
            service_client_secret=_required("SERVICE_CLIENT_SECRET"),
            rabbitmq_url=_required("RABBITMQ_URL"),
            kafka_bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            identity_url=os.getenv("IDENTITY_URL", "http://identity:8000"),
            service_client_id=os.getenv("SERVICE_CLIENT_ID", "intake"),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass(frozen=True)
class ReconcileSettings:
    """The reconciliation command reads intake_db and asks lead-core, nothing else:
    no broker, so it also runs from the API container."""

    database_url: str = field(repr=False)
    lead_core_url: str
    service_client_secret: str = field(repr=False)
    identity_url: str = "http://identity:8000"
    service_client_id: str = "intake"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            lead_core_url=_required("LEAD_CORE_URL"),
            service_client_secret=_required("SERVICE_CLIENT_SECRET"),
            identity_url=os.getenv("IDENTITY_URL", "http://identity:8000"),
            service_client_id=os.getenv("SERVICE_CLIENT_ID", "intake"),
        )
