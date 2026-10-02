from collections.abc import Callable

from chassis.auth import AUDIENCE, ISSUER, JwksCache, TokenVerifier, http_jwks
from chassis.persistence import RawSqlDatabase

from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from infrastructure.config.settings import Settings


class Container:
    """Single place where concrete implementations are chosen. Builds nothing that touches the network."""

    def __init__(self, settings: Settings, jwks_fetch: Callable[[], dict] | None = None) -> None:
        self.database = RawSqlDatabase(settings.database_url)
        # The pool and the JWKS fetch are lazy: the first use opens them, not construction.
        self.token_verifier = TokenVerifier(
            JwksCache(jwks_fetch or http_jwks(settings.jwks_url)), issuer=ISSUER, audience=AUDIENCE
        )

    def unit_of_work(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self.database)
