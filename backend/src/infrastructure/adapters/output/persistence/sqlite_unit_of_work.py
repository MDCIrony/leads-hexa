import sqlite3
from typing import Optional

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import RawSqlAgentRepository

class SqliteUnitOfWork(UnitOfWorkPort):
    def __init__(self, db: RawSqlDatabase) -> None:
        self.db = db
        self.connection: Optional[sqlite3.Connection] = None

    def __enter__(self) -> 'SqliteUnitOfWork':
        self.connection = self.db.get_connection()
        self.connection.execute("BEGIN TRANSACTION")
        
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
