"""Use-case wiring for the API. It lives here, not in the container: a use case
holds a unit of work, so each request builds its own."""
from fastapi import Depends

from application.ports.input.jobs import GetIntakeJobInputPort, GetIntakeJobsInputPort, ReprocessIntakeJobInputPort
from application.ports.input.reception import IngestLeadInputPort, ReceiveIntakeInputPort
from application.ports.input.records import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    GetIntakeStatsInputPort,
    PromoteIntakeRecordInputPort,
)
from application.ports.input.sources import (
    CreateLeadSourceInputPort,
    DeleteLeadSourceInputPort,
    GetLeadSourcesInputPort,
    UpdateLeadSourceInputPort,
)
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.jobs.manage_jobs import (
    GetIntakeJobsUseCase,
    GetIntakeJobUseCase,
    ReprocessIntakeJobUseCase,
)
from application.use_cases.reception.receive_intake import ReceiveIntakeUseCase
from application.use_cases.records.ingest_lead import IngestLeadUseCase
from application.use_cases.records.intake_stats import GetIntakeStatsUseCase
from application.use_cases.records.manage_records import (
    DiscardIntakeRecordUseCase,
    GetIntakeRecordsUseCase,
    PromoteIntakeRecordUseCase,
)
from application.use_cases.sources.lead_sources import (
    CreateLeadSourceUseCase,
    DeleteLeadSourceUseCase,
    GetLeadSourcesUseCase,
    UpdateLeadSourceUseCase,
)
from infrastructure.adapters.input.api.dependencies import get_container
from infrastructure.di.container import Container


def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()


def get_create_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateLeadSourceInputPort:
    return CreateLeadSourceUseCase(uow=uow)


def get_get_lead_sources_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadSourcesInputPort:
    return GetLeadSourcesUseCase(uow=uow)


def get_update_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateLeadSourceInputPort:
    return UpdateLeadSourceUseCase(uow=uow)


def get_delete_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteLeadSourceInputPort:
    return DeleteLeadSourceUseCase(uow=uow)


def get_receive_intake_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> ReceiveIntakeInputPort:
    return ReceiveIntakeUseCase(uow=uow)


def get_ingest_lead_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), container: Container = Depends(get_container),
) -> IngestLeadInputPort:
    return IngestLeadUseCase(uow=uow, admission=container.lead_admission)


def get_get_intake_records_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeRecordsInputPort:
    return GetIntakeRecordsUseCase(uow=uow)


def get_promote_intake_record_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), ingest: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
) -> PromoteIntakeRecordInputPort:
    return PromoteIntakeRecordUseCase(uow=uow, ingest=ingest)


def get_discard_intake_record_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DiscardIntakeRecordInputPort:
    return DiscardIntakeRecordUseCase(uow=uow)


def get_get_intake_jobs_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeJobsInputPort:
    return GetIntakeJobsUseCase(uow=uow)


def get_get_intake_job_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeJobInputPort:
    return GetIntakeJobUseCase(uow=uow)


def get_reprocess_intake_job_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> ReprocessIntakeJobInputPort:
    return ReprocessIntakeJobUseCase(uow=uow)


def get_get_intake_stats_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeStatsInputPort:
    return GetIntakeStatsUseCase(uow=uow)
