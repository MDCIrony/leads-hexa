from application.dtos.tenants import CreateTenantCommand, TenantWithManagerResult
from application.ports.input.tenants import CreateTenantInputPort
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.agents.commands import save_and_record
from domain.agents.agent import Agent, normalize_email
from domain.events.identity_events import TenantState
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant, slugify
from domain.value_objects.agent_role import AgentRole


class CreateTenantUseCase(CreateTenantInputPort):
    """Creates an organization together with its first manager, in one transaction:
    an organization nobody can log into is not a useful intermediate state.

    Its default lead sources are no longer created here: the leads side creates them
    when it hears the TenantState this records."""

    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateTenantCommand) -> TenantWithManagerResult:
        manager_email = normalize_email(command.manager_email)
        with self.uow:
            if self.uow.tenants.get_by_slug(slugify(command.name)):
                raise DomainException(
                    "Ya existe una organización con ese nombre", error_code="TENANT_ALREADY_EXISTS"
                )
            if self.uow.agents.get_by_email(manager_email):
                raise DomainException(
                    "Ya existe un usuario con ese correo electrónico", error_code="EMAIL_ALREADY_EXISTS"
                )
            tenant = self.uow.tenants.save(Tenant.create(name=command.name))
            self.uow.outbox.record(TenantState.of(tenant), channel="internal")
            manager = save_and_record(self.uow, Agent.create(
                name=command.manager_name,
                email=manager_email,
                role=AgentRole.MANAGER,
                hashed_password=self.password_hasher.hash(command.manager_password),
                tenant_id=tenant.id,
            ))
        return TenantWithManagerResult(tenant=tenant, manager=manager)
