import os
from dataclasses import dataclass, field
from typing import List

# `http://localhost` without a port is what a browser actually sends when the
# SPA is served on port 80; omitting it breaks the CORS preflight.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost,http://localhost:80"


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_expires_minutes: int = 60
    webhook_timeout_seconds: float = 5.0
    outbox_relay_interval_seconds: float = 1.0
    cors_origins: List[str] = field(default_factory=list)

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required and has no default")

        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            raise ValueError("JWT_SECRET is required and has no default")

        raw_origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return cls(
            database_url=database_url,
            jwt_secret=jwt_secret,
            jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES", "60")),
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            outbox_relay_interval_seconds=float(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "1.0")),
            cors_origins=origins,
        )
