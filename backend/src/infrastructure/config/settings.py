import os
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlsplit

# `http://localhost` without a port is what a browser actually sends when the
# SPA is served on port 80; omitting it breaks the CORS preflight.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost,http://localhost:80"


@dataclass(frozen=True)
class OAuthProviderSettings:
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""

    @property
    def enabled(self) -> bool:
        if not all((self.client_id.strip(), self.client_secret.strip(), self.redirect_uri.strip())):
            return False
        try:
            uri = urlsplit(self.redirect_uri)
        except ValueError:
            return False
        return (
            not uri.username
            and not uri.password
            and not uri.query
            and not uri.fragment
            and bool(uri.hostname)
            and (uri.scheme == "https" or (uri.scheme == "http" and uri.hostname == "localhost"))
        )


def _is_origin(value: str) -> bool:
    try:
        uri = urlsplit(value)
    except ValueError:
        return False
    return bool(
        uri.scheme in {"http", "https"}
        and uri.hostname
        and not uri.username
        and not uri.password
        and not uri.path
        and not uri.query
        and not uri.fragment
    )


@dataclass(frozen=True)
class Settings:
    database_url: str
    mfa_encryption_key: str = ""
    frontend_origin: str = "http://localhost"
    google_oauth: OAuthProviderSettings = field(default_factory=OAuthProviderSettings)
    github_oauth: OAuthProviderSettings = field(default_factory=OAuthProviderSettings)
    oauth_test_mode: bool = False
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
        mfa_encryption_key = os.getenv("MFA_ENCRYPTION_KEY")
        if not mfa_encryption_key:
            raise ValueError("MFA_ENCRYPTION_KEY is required and has no default")

        raw_origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost").strip()
        if not _is_origin(frontend_origin) or frontend_origin not in origins:
            raise ValueError("FRONTEND_ORIGIN must be an origin included in CORS_ORIGINS")

        oauth_test_mode = os.getenv("OAUTH_TEST_MODE", "false").lower() == "true"
        if oauth_test_mode and os.getenv("APP_ENV") != "test":
            raise ValueError("OAUTH_TEST_MODE requires APP_ENV=test")

        # The deterministic adapter exists solely for a loopback process the
        # HTTP harness starts. It cannot be enabled in a normal environment.
        test_google = OAuthProviderSettings(
            "e2e-test-client", "e2e-test-placeholder",
            "http://localhost/api/v1/auth/oauth/google/callback",
        )
        return cls(
            database_url=database_url,
            mfa_encryption_key=mfa_encryption_key,
            frontend_origin=frontend_origin,
            google_oauth=test_google if oauth_test_mode else OAuthProviderSettings(
                client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
                redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
            ),
            github_oauth=OAuthProviderSettings(
                client_id=os.getenv("GITHUB_CLIENT_ID", ""),
                client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
                redirect_uri=os.getenv("GITHUB_REDIRECT_URI", ""),
            ),
            oauth_test_mode=oauth_test_mode,
            session_hours=int(os.getenv("SESSION_HOURS", "8")),
            session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_external_bootstrap_servers=os.getenv("KAFKA_EXTERNAL_BOOTSTRAP_SERVERS", "localhost:9094"),
            rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"),
            cors_origins=origins,
        )
