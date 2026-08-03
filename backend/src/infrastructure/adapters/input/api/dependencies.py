from typing import Generator
from fastapi import Request, Depends
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.sqlite_unit_of_work import SqliteUnitOfWork

def get_ingest_lead_use_case(request: Request) -> IngestLeadInputPort:
    return request.app.state.ingest_lead_use_case

def get_process_batch_use_case(request: Request) -> ProcessBatchInputPort:
    return request.app.state.process_batch_use_case

def get_db(request: Request) -> RawSqlDatabase:
    return request.app.state.db

def get_uow(db: RawSqlDatabase = Depends(get_db)) -> Generator[UnitOfWorkPort, None, None]:
    uow = SqliteUnitOfWork(db)
    yield uow
