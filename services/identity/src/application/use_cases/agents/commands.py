import logging
from uuid import UUID

from application.dtos.agents import CreateAgentCommand, GetAgentQuery, UpdateAgentCommand
from application.ports.input.agents import CreateAgentInputPort, DeactivateAgentInputPort, UpdateAgentInputPort
from application.ports.output.messaging import MessagingCredentialProvisionerPort, MessagingProvisioningError
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.agents.agent import Agent, normalize_email
from domain.events.identity_events import AgentState
from domain.exceptions import AgentNotFoundException, DomainException
from domain.value_objects.agent_role import AgentRole

_LOGGER = logging.getLogger(__name__)


def _get_owned_agent(uow: UnitOfWorkPort, tenant_id: UUID, agent_id: UUID) -> Agent:
    # Scoped by tenant so an agent of another organization reads back as missing.
    agent = uow.agents.get_by_id_and_tenant(agent_id, tenant_id)
    if agent is None:
        raise AgentNotFoundException()
    return agent


def save_and_record(uow: UnitOfWorkPort, agent: Agent) -> Agent:
    # Every agent write records its new state in the same transaction: services
    # that keep a copy of the agent learn it from nowhere else.
    saved = uow.agents.save(agent)
    uow.outbox.record(AgentState.of(saved), channel="internal")
    return saved


class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateAgentCommand) -> Agent:
        email = normalize_email(command.email)
        with self.uow:
            if self.uow.agents.get_by_email(email):
                raise DomainException(
                    "Ya existe un usuario con ese correo electrónico", error_code="EMAIL_ALREADY_EXISTS"
                )
            return save_and_record(self.uow, Agent.create(
                name=command.name,
                email=email,
                is_active=command.is_active,
                role=command.role,
                hashed_password=self.password_hasher.hash(command.password),
                tenant_id=command.tenant_id,
            ))


class UpdateAgentUseCase(UpdateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateAgentCommand) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, command.tenant_id, command.agent_id)
            if command.name is not None:
                agent.name = command.name
            if command.is_active is not None:
                agent.is_active = command.is_active
            return save_and_record(self.uow, agent)


class DeactivateAgentUseCase(DeactivateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, messaging_provisioner: MessagingCredentialProvisionerPort) -> None:
        self.uow = uow
        self.messaging_provisioner = messaging_provisioner

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, query.tenant_id, query.agent_id)
            # Deactivate, never delete: leads already assigned keep pointing at it.
            agent.is_active = False
            saved = save_and_record(self.uow, agent)
        # After the commit and best-effort: Kafka's admin API is not transactional
        # with Postgres, and a failed revoke must not undo a deactivation that already
        # killed the API key. A broker that is down leaves an orphaned Kafka
        # credential until a manual retry (known gap).
        if saved.role == AgentRole.INTEGRATION:
            try:
                self.messaging_provisioner.revoke_tenant_credential(query.tenant_id)
            except MessagingProvisioningError:
                _LOGGER.warning("Could not revoke Kafka credential for tenant %s", query.tenant_id, exc_info=True)
        return saved
