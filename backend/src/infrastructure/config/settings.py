import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    # Where identity publishes the keys that sign the gateway's internal bearer.
    jwks_url: str
    webhook_timeout_seconds: float = 5.0
    outbox_relay_interval_seconds: float = 1.0
    # Defaulted, never required (ADR-0026): the backend must start and serve
    # leads even when no Kafka broker is reachable, and the relay is what
    # retries delivery once one is.
    kafka_bootstrap_servers: str = "localhost:9092"
    # Same reasoning, same default-not-required shape (ADR-0027): an
    # unreachable RabbitMQ degrades the ingest endpoint to in-process work
    # instead of failing it.
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/%2F"
    identity_url: str = "http://identity:8000"
    service_client_id: str = "lead-core"
    # Empty is allowed here because the worker never calls identity; the API refuses to start without it.
    service_client_secret: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        def required(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise ValueError(f"{name} is required and has no default")
            return value

        return cls(
            database_url=required("DATABASE_URL"),
            jwks_url=required("JWKS_URL"),
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"),
            identity_url=os.getenv("IDENTITY_URL", "http://identity:8000"),
            service_client_id=os.getenv("SERVICE_CLIENT_ID", "lead-core"),
            service_client_secret=os.getenv("SERVICE_CLIENT_SECRET", ""),
        )
