from uuid import UUID

from application.dtos.sources import (
    CreateLeadSourceCommand,
    GetLeadSourcesQuery,
    LeadSourcesPageResult,
    UpdateLeadSourceCommand,
)
from application.ports.input.sources import (
    CreateLeadSourceInputPort,
    DeleteLeadSourceInputPort,
    GetLeadSourcesInputPort,
    UpdateLeadSourceInputPort,
)
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.sources.lead_source import LeadSource

# MVP scale: an organization holds a handful of sources, so scanning them all
# to check a name is simpler than a dedicated lookup on the repository port.
_EFFECTIVELY_UNBOUNDED = 10_000


def _get_owned_source(uow: UnitOfWorkPort, tenant_id: UUID, source_id: UUID) -> LeadSource:
    """A source of another organization reads back as missing, never as a 403 that would confirm it exists."""
    source = uow.sources.get_by_id_and_tenant(source_id, tenant_id)
    if source is None:
        raise DomainException("El origen no existe", error_code="SOURCE_NOT_FOUND")
    return source


class CreateLeadSourceUseCase(CreateLeadSourceInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: CreateLeadSourceCommand) -> LeadSource:
        with self.uow:
            clean_name = (command.name or "").strip()
            existing = self.uow.sources.list_by_tenant(command.tenant_id, limit=_EFFECTIVELY_UNBOUNDED)
            if any(s.name == clean_name for s in existing):
                raise DomainException(
                    "Ya existe un origen con ese nombre en la organización",
                    error_code="SOURCE_ALREADY_EXISTS",
                )
            source = LeadSource.create(
                tenant_id=command.tenant_id,
                name=command.name,
                kind=command.kind,
                field_mapping=command.field_mapping,
            )
            return self.uow.sources.save(source)


class GetLeadSourcesUseCase(GetLeadSourcesInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetLeadSourcesQuery) -> LeadSourcesPageResult:
        with self.uow:
            items = self.uow.sources.list_by_tenant(query.tenant_id, limit=query.limit, offset=query.offset)
            total = len(self.uow.sources.list_by_tenant(query.tenant_id, limit=_EFFECTIVELY_UNBOUNDED))
        return LeadSourcesPageResult(items=items, total=total)


class UpdateLeadSourceUseCase(UpdateLeadSourceInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateLeadSourceCommand) -> LeadSource:
        with self.uow:
            source = _get_owned_source(self.uow, command.tenant_id, command.source_id)
            if command.name is not None:
                source.rename(command.name)
            if command.field_mapping is not None:
                source.update_mapping(command.field_mapping)
            if command.is_active is not None:
                source.activate() if command.is_active else source.deactivate()
            return self.uow.sources.save(source)


class DeleteLeadSourceUseCase(DeleteLeadSourceInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, source_id: UUID) -> None:
        with self.uow:
            _get_owned_source(self.uow, tenant_id, source_id)
            # A source is in use while any record or job points at it: both
            # reference it, and a record's job_id is nullable, so neither count
            # covers the other. Its leads live in another service and no longer constrain it.
            if (self.uow.intake_records.count_by_source(tenant_id, source_id) > 0
                    or self.uow.intake_jobs.count_by_source(tenant_id, source_id) > 0):
                raise DomainException(
                    "El origen tiene registros o trabajos de recepción asociados y no puede eliminarse",
                    error_code="SOURCE_IN_USE",
                )
            self.uow.sources.delete(source_id, tenant_id)
