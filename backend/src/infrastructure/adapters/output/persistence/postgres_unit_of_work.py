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

    def __enter__(self) -> "PostgresUnitOfWork":
        # With autocommit disabled, psycopg opens a transaction implicitly on
        # the first statement — no explicit BEGIN needed, unlike sqlite3.
        self.connection = self.db.get_connection(autocommit=False)

        self.leads = RawSqlLeadRepository(self.connection)
        self.rules = RawSqlRuleRepository(self.connection)
        self.agents = RawSqlAgentRepository(self.connection)
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
