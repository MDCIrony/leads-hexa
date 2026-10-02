from application.dtos.tenants import GetTenantsQuery, TenantsPageResult, TenantSummary, UpdateTenantCommand
from application.ports.input.tenants import GetTenantsInputPort, UpdateTenantInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.events.identity_events import AgentState, TenantState
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant


class GetTenantsUseCase(GetTenantsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetTenantsQuery) -> TenantsPageResult:
        with self.uow:
            tenants = self.uow.tenants.list_all(limit=query.limit, offset=query.offset)
            total = self.uow.tenants.count_all()
            items = [
                TenantSummary(tenant=tenant, agent_count=self.uow.tenants.count_active_agents(tenant.id.value))
                for tenant in tenants
            ]
        return TenantsPageResult(items=items, total=total)


class UpdateTenantUseCase(UpdateTenantInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateTenantCommand) -> Tenant:
        with self.uow:
            tenant = self.uow.tenants.get_by_id(command.tenant_id)
            if tenant is None:
                raise DomainException("La organización no existe", error_code="TENANT_NOT_FOUND")
            if command.name is not None:
                tenant.rename(command.name)
            if command.is_active is True:
                tenant.activate()
            elif command.is_active is False:
                tenant.deactivate()
                # A suspended organization must not leave working credentials behind.
                for agent in self.uow.agents.deactivate_all_by_tenant(command.tenant_id):
                    self.uow.outbox.record(AgentState.of(agent), channel="internal")
            tenant = self.uow.tenants.save(tenant)
            self.uow.outbox.record(TenantState.of(tenant), channel="internal")
        return tenant
