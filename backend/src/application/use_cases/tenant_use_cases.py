from application.dtos.commands import (
    CreateTenantCommand,
    TenantSummary,
    TenantWithManagerResult,
    TenantsPageResult,
    UpdateTenantCommand,
)
from application.dtos.queries import GetTenantsQuery
from application.ports.input.tenant_use_case_ports import (
    CreateTenantInputPort,
    GetTenantsInputPort,
    UpdateTenantInputPort,
)
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent, normalize_email
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant, slugify
from domain.events.identity_events import AgentState, TenantState
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole, LeadSourceKind


class CreateTenantUseCase(CreateTenantInputPort):
    """Creates an organization together with its first manager.

    Both writes share one transaction: an organization nobody can log into is
    not a useful intermediate state."""

    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateTenantCommand) -> TenantWithManagerResult:
        manager_email = normalize_email(command.manager_email)
        with self.uow:
            if self.uow.tenants.get_by_slug(slugify(command.name)):
                raise DomainException(
                    "Ya existe una organización con ese nombre",
                    error_code="TENANT_ALREADY_EXISTS",
                )
            if self.uow.agents.get_by_email(manager_email):
                raise DomainException(
                    "Ya existe un usuario con ese correo electrónico",
                    error_code="EMAIL_ALREADY_EXISTS",
                )

            tenant = self.uow.tenants.save(Tenant.create(name=command.name))
            self.uow.outbox.record(TenantState.of(tenant), channel="internal")

            # Same transaction, same reason as the manager below: an
            # organization that cannot receive leads is not a useful
            # intermediate state.
            for name, kind in (("Formulario manual", LeadSourceKind.MANUAL_FORM),
                               ("Carga de fichero", LeadSourceKind.FILE_UPLOAD)):
                self.uow.sources.save(
                    LeadSource.create(tenant_id=tenant.id, name=name, kind=kind)
                )

            manager = self.uow.agents.save(
                Agent.create(
                    name=command.manager_name,
                    email=manager_email,
                    role=AgentRole.MANAGER,
                    hashed_password=self.password_hasher.hash(command.manager_password),
                    tenant_id=tenant.id,
                )
            )
            self.uow.outbox.record(AgentState.of(manager), channel="internal")
        return TenantWithManagerResult(tenant=tenant, manager=manager)


class GetTenantsUseCase(GetTenantsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetTenantsQuery) -> TenantsPageResult:
        with self.uow:
            tenants = self.uow.tenants.list_all(limit=query.limit, offset=query.offset)
            total = self.uow.tenants.count_all()
            items = [
                TenantSummary(
                    tenant=tenant,
                    agent_count=self.uow.tenants.count_active_agents(tenant.id.value),
                )
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
                raise DomainException(
                    "La organización no existe", error_code="TENANT_NOT_FOUND"
                )

            if command.name is not None:
                tenant.rename(command.name)

            if command.is_active is not None:
                if command.is_active:
                    tenant.activate()
                else:
                    tenant.deactivate()
                    # A suspended organization must not leave working credentials
                    # behind, so its users are deactivated with it.
                    for agent in self.uow.agents.deactivate_all_by_tenant(command.tenant_id):
                        self.uow.outbox.record(AgentState.of(agent), channel="internal")

            self.uow.tenants.save(tenant)
            self.uow.outbox.record(TenantState.of(tenant), channel="internal")
        return tenant
