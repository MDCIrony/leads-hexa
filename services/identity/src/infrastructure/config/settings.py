import os
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class ApiSettings:
    """What the API process needs. The worker gets its own settings, so neither
    has to be given the other's variables."""

    database_url: str
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> Self:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("Missing required environment variable DATABASE_URL")
        return cls(database_url=database_url, log_level=os.getenv("LOG_LEVEL", "INFO"))
