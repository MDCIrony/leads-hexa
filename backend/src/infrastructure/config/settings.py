import os
from dataclasses import dataclass, field
from typing import List

# `http://localhost` without a port is what a browser actually sends when the
# SPA is served on port 80; omitting it breaks the CORS preflight.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost,http://localhost:80"


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_hours: int = 8
    session_cookie_secure: bool = False
    webhook_timeout_seconds: float = 5.0
    outbox_relay_interval_seconds: float = 1.0
    # Defaulted, never required (ADR-0026): the backend must start and serve
    # leads even when no Kafka broker is reachable, and the relay is what
    # retries delivery once one is.
    kafka_bootstrap_servers: str = "localhost:9092"
    # What an external client is told to connect to (ADR-0028): the internal
    # kafka_bootstrap_servers above is unreachable from outside the compose
    # network, so the two must stay separate settings.
    kafka_external_bootstrap_servers: str = "localhost:9094"
    # Same reasoning, same default-not-required shape (ADR-0027): an
    # unreachable RabbitMQ degrades the ingest endpoint to in-process work
    # instead of failing it.
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/%2F"
    cors_origins: List[str] = field(default_factory=list)

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required and has no default")

        raw_origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return cls(
            database_url=database_url,
            session_hours=int(os.getenv("SESSION_HOURS", "8")),
            session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_external_bootstrap_servers=os.getenv("KAFKA_EXTERNAL_BOOTSTRAP_SERVERS", "localhost:9094"),
            rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"),
            cors_origins=origins,
        )
