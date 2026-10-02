"""One settings class per process: each requires only the variables it uses, so the
worker never holds the signing key and the API never needs a reachable broker."""
import os
from dataclasses import dataclass, field
from typing import Self

from infrastructure.config.oauth import TEST_GOOGLE_OAUTH, OAuthProviderSettings, is_origin
from infrastructure.security.service_clients import ServiceClient, parse_service_clients

# `http://localhost` without a port is what a browser actually sends when the
# SPA is served on port 80; omitting it breaks the CORS preflight.
_DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://localhost", "http://localhost:80")


def _required(name: str) -> str:
    # No fallback: a silent default is what once let the backend write to an
    # unrelated database while the real one sat empty next to it.
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required and has no default")
    return value


def _flag(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"


@dataclass(frozen=True)
class ApiSettings:
    database_url: str
    # Raw `kid=seed[,kid=seed]`; chassis parses and validates it when the Container builds.
    # Secrets stay out of repr, so logging the settings never prints them.
    signing_keys: str = field(repr=False)
    service_clients: tuple[ServiceClient, ...]
    mfa_encryption_key: str = field(repr=False)
    frontend_origin: str = "http://localhost"
    cors_origins: tuple[str, ...] = _DEFAULT_CORS_ORIGINS
    google_oauth: OAuthProviderSettings = field(default_factory=OAuthProviderSettings)
    github_oauth: OAuthProviderSettings = field(default_factory=OAuthProviderSettings)
    oauth_test_mode: bool = False
    session_hours: int = 8
    session_cookie_secure: bool = False
    # Defaulted, never required (ADR-0026): the API starts and serves logins with no
    # broker; only provisioning an integration credential needs one.
    kafka_bootstrap_servers: str = "localhost:9092"
    # What an external client is told to connect to (ADR-0028): the internal listener
    # above is unreachable from outside the compose network.
    kafka_external_bootstrap_servers: str = "localhost:9094"
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        database_url = _required("DATABASE_URL")
        signing_keys = _required("SIGNING_KEYS")
        service_clients = parse_service_clients(_required("SERVICE_CLIENTS"))
        mfa_encryption_key = _required("MFA_ENCRYPTION_KEY")

        raw_origins = os.getenv("CORS_ORIGINS", ",".join(_DEFAULT_CORS_ORIGINS))
        origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost").strip()
        if not is_origin(frontend_origin) or frontend_origin not in origins:
            raise ValueError("FRONTEND_ORIGIN must be an origin included in CORS_ORIGINS")

        oauth_test_mode = _flag("OAUTH_TEST_MODE")
        if oauth_test_mode and os.getenv("APP_ENV") != "test":
            raise ValueError("OAUTH_TEST_MODE requires APP_ENV=test")

        return cls(
            database_url=database_url,
            signing_keys=signing_keys,
            service_clients=service_clients,
            mfa_encryption_key=mfa_encryption_key,
            frontend_origin=frontend_origin,
            cors_origins=origins,
            google_oauth=TEST_GOOGLE_OAUTH if oauth_test_mode else OAuthProviderSettings.from_environment("GOOGLE"),
            github_oauth=OAuthProviderSettings.from_environment("GITHUB"),
            oauth_test_mode=oauth_test_mode,
            session_hours=int(os.getenv("SESSION_HOURS", "8")),
            session_cookie_secure=_flag("SESSION_COOKIE_SECURE"),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_external_bootstrap_servers=os.getenv("KAFKA_EXTERNAL_BOOTSTRAP_SERVERS", "localhost:9094"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    # Required here, unlike in the API: relaying the outbox is all the worker does.
    kafka_bootstrap_servers: str
    outbox_relay_interval_seconds: float = 1.0
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        return cls(
            database_url=_required("DATABASE_URL"),
            kafka_bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
