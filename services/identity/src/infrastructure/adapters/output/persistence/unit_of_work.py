from contextlib import AbstractContextManager

import psycopg
from chassis.persistence import RawSqlDatabase

from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException
from infrastructure.adapters.output.persistence.agent_repository import PostgresAgentRepository
from infrastructure.adapters.output.persistence.challenge_repository import PostgresAuthChallengeRepository
from infrastructure.adapters.output.persistence.mfa_repository import PostgresAgentMfaRepository
from infrastructure.adapters.output.persistence.outbox_repository import PostgresOutboxRepository
from infrastructure.adapters.output.persistence.session_repository import PostgresAuthSessionRepository
from infrastructure.adapters.output.persistence.social_identity_repository import PostgresSocialIdentityRepository
from infrastructure.adapters.output.persistence.tenant_repository import PostgresTenantRepository

# Only the constraint types a use case can forget to pre-check. Anything else keeps its
# type and reaches the unhandled handler as a 500.
_TRANSLATED = (
    (psycopg.errors.UniqueViolation, "Ya existe un registro con ese valor", "ALREADY_EXISTS"),
    (psycopg.errors.ForeignKeyViolation, "Referencia a un registro que no existe", "RELATED_ENTITY_NOT_FOUND"),
    (psycopg.errors.NotNullViolation, "Falta un campo obligatorio", "MISSING_REQUIRED_FIELD"),
)


class PostgresUnitOfWork(UnitOfWorkPort):
    """One transaction per `with` block; the same instance can be entered again afterwards."""

    def __init__(self, database: RawSqlDatabase) -> None:
        self._database = database
        self.connection: psycopg.Connection | None = None
        self._connection_ctx: AbstractContextManager[psycopg.Connection] | None = None

    def __enter__(self) -> "PostgresUnitOfWork":
        # Entered by hand rather than with a single `with`: the borrowed
        # connection must outlive this method and go back to the pool only when
        # the caller's own `with` block exits.
        self._connection_ctx = self._database.get_connection(autocommit=False)
        self.connection = self._connection_ctx.__enter__()
        self.agents = PostgresAgentRepository(self.connection)
        self.tenants = PostgresTenantRepository(self.connection)
        self.sessions = PostgresAuthSessionRepository(self.connection)
        self.challenges = PostgresAuthChallengeRepository(self.connection)
        self.mfa = PostgresAgentMfaRepository(self.connection)
        self.social_identities = PostgresSocialIdentityRepository(self.connection)
        self.outbox = PostgresOutboxRepository(self.connection)
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self._connection_ctx is not None:
                self._connection_ctx.__exit__(exc_type, exc_val, exc_tb)
                self._connection_ctx = None
                self.connection = None

        # Translated only after rollback and the pool return, so a raw psycopg
        # error never leaves a borrowed connection or an open transaction behind.
        for error_type, message, error_code in _TRANSLATED:
            if isinstance(exc_val, error_type):
                raise DomainException(message, error_code=error_code) from exc_val

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
