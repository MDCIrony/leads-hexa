from contextlib import AbstractContextManager

import psycopg
from chassis.persistence import RawSqlDatabase

from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException
from infrastructure.adapters.output.persistence.intake_file_repository import PostgresIntakeFileRepository
from infrastructure.adapters.output.persistence.intake_job_repository import PostgresIntakeJobRepository
from infrastructure.adapters.output.persistence.intake_record_repository import PostgresIntakeRecordRepository
from infrastructure.adapters.output.persistence.lead_source_repository import PostgresLeadSourceRepository
from infrastructure.adapters.output.persistence.outbox_repository import PostgresOutboxRepository
from infrastructure.adapters.output.persistence.processed_event_repository import PostgresProcessedEventRepository
from infrastructure.adapters.output.persistence.provisioned_tenant_repository import (
    PostgresProvisionedTenantRepository,
)

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
        self.sources = PostgresLeadSourceRepository(self.connection)
        self.intake_jobs = PostgresIntakeJobRepository(self.connection)
        self.intake_records = PostgresIntakeRecordRepository(self.connection)
        self.intake_files = PostgresIntakeFileRepository(self.connection)
        self.outbox = PostgresOutboxRepository(self.connection)
        self.processed_events = PostgresProcessedEventRepository(self.connection)
        self.provisioned_tenants = PostgresProvisionedTenantRepository(self.connection)
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
