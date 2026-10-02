"""The use cases whose composition the API and the worker share.

Built per caller, not in the container: each holds a unit of work, so each
request or job message gets its own. Plain functions, so the worker can call
them without FastAPI and the API wraps them in its dependencies."""
from application.ports.input.reception import IngestLeadInputPort, ProcessBatchInputPort, ProcessIntakeJobInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.jobs.process_intake_job import ProcessIntakeJobUseCase
from application.use_cases.reception.process_batch import ProcessBatchUseCase
from application.use_cases.records.ingest_lead import IngestLeadUseCase
from infrastructure.di.container import Container


def ingest_lead(uow: UnitOfWorkPort, container: Container) -> IngestLeadInputPort:
    return IngestLeadUseCase(uow=uow, admission=container.lead_admission)


def process_batch(uow: UnitOfWorkPort, container: Container) -> ProcessBatchInputPort:
    return ProcessBatchUseCase(uow=uow, file_parser=container.file_parser)


def process_intake_job(uow: UnitOfWorkPort, container: Container) -> ProcessIntakeJobInputPort:
    return ProcessIntakeJobUseCase(uow=uow, ingest=ingest_lead(uow, container))
