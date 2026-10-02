from contextlib import AbstractContextManager

import psycopg
from chassis.persistence import RawSqlDatabase

from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException
from infrastructure.adapters.output.persistence.member_repository import PostgresMemberRepository
from infrastructure.adapters.output.persistence.notification_repository import PostgresNotificationRepository
from infrastructure.adapters.output.persistence.processed_event_repository import PostgresProcessedEventRepository


class PostgresUnitOfWork(UnitOfWorkPort):
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
        self.notifications = PostgresNotificationRepository(self.connection)
        self.members = PostgresMemberRepository(self.connection)
        self.processed_events = PostgresProcessedEventRepository(self.connection)
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
        # These two will fail the same way on every redelivery; the other
        # constraint types of the backend cannot occur here (upserts, no foreign keys).
        if isinstance(exc_val, psycopg.errors.UniqueViolation):
            raise DomainException("A record with that value already exists", error_code="ALREADY_EXISTS") from exc_val
        if isinstance(exc_val, psycopg.errors.NotNullViolation):
            raise DomainException("A required field is missing", error_code="MISSING_REQUIRED_FIELD") from exc_val

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
