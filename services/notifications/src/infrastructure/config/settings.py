import os
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwks_url: str
    kafka_bootstrap_servers: str
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        def required(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise ValueError(f"Missing required environment variable {name}")
            return value

        return cls(
            database_url=required("DATABASE_URL"),
            jwks_url=required("JWKS_URL"),
            kafka_bootstrap_servers=required("KAFKA_BOOTSTRAP_SERVERS"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
