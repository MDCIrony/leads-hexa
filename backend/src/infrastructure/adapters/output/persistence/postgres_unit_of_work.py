from contextlib import AbstractContextManager
from typing import Optional

import psycopg

from application.ports.output.unit_of_work_port import UnitOfWorkPort
# infrastructure → domain is an allowed direction; the inverse is not.
from domain.exceptions import DomainException
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_disqualification_rule_repository import (
    RawSqlDisqualificationRuleRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import RawSqlAgentRepository
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import RawSqlSalesGroupRepository
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import RawSqlTenantRepository
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import RawSqlLeadSourceRepository
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import RawSqlIntakeRecordRepository
from infrastructure.adapters.output.persistence.raw_sql_intake_job_repository import RawSqlIntakeJobRepository
from infrastructure.adapters.output.persistence.raw_sql_notification_repository import (
    RawSqlNotificationRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_outbox_repository import RawSqlOutboxRepository


class PostgresUnitOfWork(UnitOfWorkPort):
    def __init__(self, db: RawSqlDatabase) -> None:
        self.db = db
        self.connection: Optional[psycopg.Connection] = None
        self._connection_ctx: Optional[AbstractContextManager[psycopg.Connection]] = None

    def __enter__(self) -> "PostgresUnitOfWork":
        # With autocommit disabled, psycopg opens a transaction implicitly on
        # the first statement — no explicit BEGIN needed, unlike sqlite3.
        # get_connection() is now a pool-backed context manager; it is
        # entered/exited manually (rather than via a single `with`) because
        # the borrowed connection must outlive this method and only be
        # released once the caller's `with self.uow:` block exits.
        self._connection_ctx = self.db.get_connection(autocommit=False)
        self.connection = self._connection_ctx.__enter__()

        self.leads = RawSqlLeadRepository(self.connection)
        self.rules = RawSqlRuleRepository(self.connection)
        self.disqualification_rules = RawSqlDisqualificationRuleRepository(self.connection)
        self.agents = RawSqlAgentRepository(self.connection)
        self.tenants = RawSqlTenantRepository(self.connection)
        self.groups = RawSqlSalesGroupRepository(self.connection)
        self.sources = RawSqlLeadSourceRepository(self.connection)
        self.intake_records = RawSqlIntakeRecordRepository(self.connection)
        self.intake_jobs = RawSqlIntakeJobRepository(self.connection)
        self.notifications = RawSqlNotificationRepository(self.connection)
        self.outbox = RawSqlOutboxRepository(self.connection)
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self._connection_ctx is not None:
                # commit()/rollback() above already ended the transaction;
                # this just returns the connection to the pool.
                self._connection_ctx.__exit__(exc_type, exc_val, exc_tb)
                self._connection_ctx = None
                self.connection = None

        # Translated only after rollback and pool return have both happened,
        # so a raw psycopg error never leaves a borrowed connection or an open
        # transaction behind. Only the constraint types a use case can forget
        # to pre-check are covered; anything else keeps its original type and
        # reaches unhandled_exception_handler as a 500, unchanged. A message
        # consumer needs the difference: a 500 reads as "retry me", and these
        # four will fail exactly the same way on every redelivery.
        if isinstance(exc_val, psycopg.errors.UniqueViolation):
            raise DomainException(
                "Ya existe un registro con ese valor", error_code="ALREADY_EXISTS"
            ) from exc_val
        if isinstance(exc_val, psycopg.errors.ForeignKeyViolation):
            raise DomainException(
                "Referencia a un registro que no existe", error_code="RELATED_ENTITY_NOT_FOUND"
            ) from exc_val
        if isinstance(exc_val, psycopg.errors.NotNullViolation):
            raise DomainException(
                "Falta un campo obligatorio", error_code="MISSING_REQUIRED_FIELD"
            ) from exc_val
        # Money accepts any finite non-negative amount, but leads.budget is
        # NUMERIC(14, 2): a figure above 10^12 clears the domain and dies at
        # the insert. Untranslated it reached the client as a 500, which reads
        # as "try again" for a value that will overflow on every attempt.
        if isinstance(exc_val, psycopg.errors.NumericValueOutOfRange):
            raise DomainException(
                "El importe excede el máximo admitido", error_code="AMOUNT_OUT_OF_RANGE"
            ) from exc_val

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
