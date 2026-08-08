from contextlib import AbstractContextManager
from typing import Optional

import psycopg

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import RawSqlAgentRepository


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
        self.agents = RawSqlAgentRepository(self.connection)
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

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
