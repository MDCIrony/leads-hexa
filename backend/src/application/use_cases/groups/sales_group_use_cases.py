from uuid import UUID

from application.dtos.commands import (
    CreateSalesGroupCommand,
    SalesGroupsPageResult,
    SalesGroupSummary,
    UpdateSalesGroupCommand,
)
from application.dtos.queries import GetSalesGroupsQuery
from application.ports.input.groups.sales_group_use_case_ports import (
    CreateSalesGroupInputPort,
    DeleteSalesGroupInputPort,
    GetSalesGroupsInputPort,
    UpdateSalesGroupInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.groups.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.enums import AssignmentStrategy

# MVP scale: a tenant is expected to hold a handful of groups, so scanning
# all of them to check a name is simpler than adding a dedicated lookup to the
# repository port for just this.
_EFFECTIVELY_UNBOUNDED = 10_000


def get_owned_group(uow: UnitOfWorkPort, tenant_id: UUID, group_id: UUID) -> SalesGroup:
    """A group from another organization must read back as missing, never as
    a 403 that would confirm it exists elsewhere."""
    group = uow.groups.get_by_id(group_id)
    if group is None or str(group.tenant_id) != str(tenant_id):
        raise DomainException("El grupo no existe", error_code="GROUP_NOT_FOUND")
    return group


class CreateSalesGroupUseCase(CreateSalesGroupInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: CreateSalesGroupCommand) -> SalesGroup:
        with self.uow:
            clean_name = (command.name or "").strip()
            existing = self.uow.groups.list_by_tenant(
                command.tenant_id, limit=_EFFECTIVELY_UNBOUNDED
            )
            if any(g.name == clean_name for g in existing):
                raise DomainException(
                    "Ya existe un grupo con ese nombre en la organización",
                    error_code="GROUP_ALREADY_EXISTS",
                )
            group = SalesGroup.create(
                tenant_id=command.tenant_id,
                name=command.name,
                description=command.description,
                default_strategy=command.default_strategy,
                capacity_per_agent=command.capacity_per_agent,
            )
            return self.uow.groups.save(group)


class GetSalesGroupsUseCase(GetSalesGroupsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetSalesGroupsQuery) -> SalesGroupsPageResult:
        with self.uow:
            groups = self.uow.groups.list_by_tenant(
                query.tenant_id, limit=query.limit, offset=query.offset
            )
            total = self.uow.groups.count_by_tenant(query.tenant_id)
            items = [
                SalesGroupSummary(
                    group=group,
                    agent_count=self.uow.advisors.count_by_group(query.tenant_id, group.id.value),
                )
                for group in groups
            ]
        return SalesGroupsPageResult(items=items, total=total)


class UpdateSalesGroupUseCase(UpdateSalesGroupInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateSalesGroupCommand) -> SalesGroup:
        with self.uow:
            group = get_owned_group(self.uow, command.tenant_id, command.group_id)
            if command.name is not None:
                group.rename(command.name)
            if command.description is not None:
                group.description = command.description
            if command.default_strategy is not None:
                group.default_strategy = AssignmentStrategy(command.default_strategy)
            if command.capacity_per_agent is not None:
                group.capacity_per_agent = command.capacity_per_agent
            if command.is_active is not None:
                # Unlike deactivating an organization, this never cascades to
                # the group's agents: they keep working what is already
                # assigned to them, they just stop receiving new leads.
                group.activate() if command.is_active else group.deactivate()
            return self.uow.groups.save(group)


class DeleteSalesGroupUseCase(DeleteSalesGroupInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, group_id: UUID) -> None:
        with self.uow:
            get_owned_group(self.uow, tenant_id, group_id)
            # Its advisors are orphaned by the foreign key (ON DELETE SET NULL,
            # migrations 003 and 017), not by a loop here: group_id is not
            # identity data, so no agent event has anything to announce.
            self.uow.groups.delete(group_id)
