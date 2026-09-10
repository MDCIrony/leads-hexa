import logging
import secrets

from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.dtos.commands import (
    AgentsPageResult,
    CreateAgentCommand,
    IntegrationCredentialResult,
    IssueIntegrationCredentialCommand,
    UpdateAgentCommand,
)
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort,
    DeactivateAgentInputPort,
    GetAgentInputPort,
    GetAgentsInputPort,
    IssueIntegrationCredentialInputPort,
    UpdateAgentInputPort,
)
from application.ports.output.messaging_credential_provisioner_port import (
    MessagingCredentialProvisionerPort,
    MessagingProvisioningError,
    kafka_username,
)
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent, normalize_email
from domain.exceptions import AgentNotFoundException, DomainException
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId

_LOGGER = logging.getLogger(__name__)

class GetAgentsUseCase(GetAgentsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentsQuery) -> AgentsPageResult:
        with self.uow:
            items = self.uow.agents.list_by_tenant(
                query.tenant_id,
                group_id=query.group_id,
                is_active=query.is_active,
                limit=query.limit,
                offset=query.offset,
            )
            # Both calls need the same filter, or total counts a different
            # population than items lists and has_more lies.
            total = self.uow.agents.count_by_tenant(
                query.tenant_id, group_id=query.group_id, is_active=query.is_active
            )
        return AgentsPageResult(items=items, total=total)

class GetAgentUseCase(GetAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = self.uow.agents.get_by_id_and_tenant(query.agent_id, query.tenant_id)
        if agent is None:
            raise AgentNotFoundException()
        return agent

class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort):
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateAgentCommand) -> Agent:
        email = normalize_email(command.email)
        with self.uow:
            if self.uow.agents.get_by_email(email):
                raise DomainException(
                    "Ya existe un usuario con ese correo electrónico",
                    error_code="EMAIL_ALREADY_EXISTS",
                )
            agent = Agent.create(
                name=command.name,
                email=email,
                group_id=command.group_id,
                is_active=command.is_active,
                role=command.role,
                hashed_password=self.password_hasher.hash(command.password),
                tenant_id=command.tenant_id,
            )
            return self.uow.agents.save(agent)


def _integration_email(tenant) -> str:
    # .invalid is reserved by RFC 2606 for addresses that must never resolve,
    # which is exactly what a deterministic, non-human account needs.
    return f"integration@{tenant.slug}.invalid"


class IssueIntegrationCredentialUseCase(IssueIntegrationCredentialInputPort):
    """Upsert, not create-then-rotate: one call either mints the organization's
    machine credential or replaces its secret, so there is exactly one path
    instead of two that could drift apart (ADR-0028)."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        messaging_provisioner: MessagingCredentialProvisionerPort,
    ):
        self.uow = uow
        self.password_hasher = password_hasher
        self.messaging_provisioner = messaging_provisioner

    def execute(self, command: IssueIntegrationCredentialCommand) -> IntegrationCredentialResult:
        with self.uow:
            tenant = self.uow.tenants.get_by_id(command.tenant_id)
        if tenant is None:
            raise DomainException("La organización no existe", error_code="TENANT_NOT_FOUND")

        # Kafka first, deliberately outside any Postgres transaction: if the
        # broker cannot take the credential, nothing about the agent should
        # change either. Issuing an API key whose matching Kafka credential
        # does not exist is the exact "seguridad de teatro" ADR-0028 closes.
        try:
            kafka_password = self.messaging_provisioner.issue_tenant_credential(command.tenant_id)
        except MessagingProvisioningError as error:
            raise DomainException(
                "El aprovisionamiento de Kafka no está disponible; inténtalo de nuevo",
                error_code="MESSAGING_UNAVAILABLE",
            ) from error

        api_secret = secrets.token_urlsafe(32)
        hashed = self.password_hasher.hash(api_secret)
        email = _integration_email(tenant)
        with self.uow:
            existing = self.uow.agents.get_by_email(email)
            if existing is not None:
                existing.hashed_password = hashed
                existing.is_active = True
                agent = self.uow.agents.save(existing)
            else:
                agent = self.uow.agents.save(Agent.create(
                    name=f"Integración · {tenant.name}",
                    email=email,
                    role=AgentRole.INTEGRATION,
                    hashed_password=hashed,
                    tenant_id=command.tenant_id,
                ))

        return IntegrationCredentialResult(
            agent=agent,
            api_key=f"{agent.id}.{api_secret}",
            kafka_username=kafka_username(command.tenant_id),
            kafka_password=kafka_password,
            kafka_topic=f"leads.{command.tenant_id}",
        )


def _get_owned_agent(uow: UnitOfWorkPort, tenant_id, agent_id) -> Agent:
    """Scoped through get_by_id_and_tenant so an agent belonging to another
    organization reads back as missing rather than confirming it exists."""
    agent = uow.agents.get_by_id_and_tenant(agent_id, tenant_id)
    if agent is None:
        raise AgentNotFoundException()
    return agent


class UpdateAgentUseCase(UpdateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: UpdateAgentCommand) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, command.tenant_id, command.agent_id)
            if command.name is not None:
                agent.name = command.name
            if command.group_id is not None:
                group = self.uow.groups.get_by_id(command.group_id)
                if group is None or str(group.tenant_id) != str(command.tenant_id):
                    raise DomainException(
                        "El grupo no existe", error_code="GROUP_NOT_FOUND"
                    )
                agent.group_id = GroupId(command.group_id)
            if command.is_active is not None:
                agent.is_active = command.is_active
            return self.uow.agents.save(agent)


class DeactivateAgentUseCase(DeactivateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, messaging_provisioner: MessagingCredentialProvisionerPort):
        self.uow = uow
        self.messaging_provisioner = messaging_provisioner

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, query.tenant_id, query.agent_id)
            # Deactivate, never delete: leads already assigned to this agent
            # keep pointing at it, and get_available_agents already filters
            # on is_active, so it simply stops receiving new ones.
            agent.is_active = False
            saved = self.uow.agents.save(agent)
        # Outside the transaction and best-effort, on purpose: Kafka's admin
        # API is not transactional with Postgres, and a revoke that fails
        # here must not roll back the deactivation that already committed —
        # the API key is already dead either way. A broker that is down when
        # this runs leaves an orphaned Kafka credential until the next manual
        # retry; declared as a known gap (see Riesgos), same tier as "nadie
        # mira la DLQ" elsewhere in this codebase.
        if saved.role == AgentRole.INTEGRATION:
            try:
                self.messaging_provisioner.revoke_tenant_credential(query.tenant_id)
            except MessagingProvisioningError:
                _LOGGER.warning("Could not revoke Kafka credential for tenant %s", query.tenant_id, exc_info=True)
        return saved
