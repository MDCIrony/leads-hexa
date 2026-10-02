import secrets

from application.dtos.agents import IntegrationCredentialResult, IssueIntegrationCredentialCommand
from application.ports.input.agents import IssueIntegrationCredentialInputPort
from application.ports.output.messaging import (
    MessagingCredentialProvisionerPort,
    MessagingProvisioningError,
    kafka_username,
)
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.agents.commands import save_and_record
from domain.agents.agent import Agent
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole


def _integration_email(tenant: Tenant) -> str:
    # .invalid is reserved by RFC 2606 for addresses that must never resolve,
    # which is what a deterministic, non-human account needs.
    return f"integration@{tenant.slug}.invalid"


class IssueIntegrationCredentialUseCase(IssueIntegrationCredentialInputPort):
    """Upsert, not create-then-rotate: one call mints the organization's machine
    credential or replaces its secret, one path instead of two that drift (ADR-0028)."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        messaging_provisioner: MessagingCredentialProvisionerPort,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.messaging_provisioner = messaging_provisioner

    def execute(self, command: IssueIntegrationCredentialCommand) -> IntegrationCredentialResult:
        with self.uow:
            tenant = self.uow.tenants.get_by_id(command.tenant_id)
        if tenant is None:
            raise DomainException("La organización no existe", error_code="TENANT_NOT_FOUND")

        # Kafka first and outside any transaction: an API key whose Kafka credential
        # does not exist is exactly the false security ADR-0028 closes.
        try:
            kafka_password = self.messaging_provisioner.issue_tenant_credential(command.tenant_id)
        except MessagingProvisioningError as error:
            raise DomainException(
                "El aprovisionamiento de Kafka no está disponible; inténtalo de nuevo",
                error_code="MESSAGING_UNAVAILABLE",
            ) from error

        api_secret = secrets.token_urlsafe(32)
        hashed = self.password_hasher.hash(api_secret)
        with self.uow:
            agent = self.uow.agents.get_by_email(_integration_email(tenant))
            if agent is not None:
                agent.hashed_password = hashed
                agent.is_active = True
            else:
                agent = Agent.create(
                    name=f"Integración · {tenant.name}",
                    email=_integration_email(tenant),
                    role=AgentRole.INTEGRATION,
                    hashed_password=hashed,
                    tenant_id=command.tenant_id,
                )
            agent = save_and_record(self.uow, agent)

        return IntegrationCredentialResult(
            agent=agent,
            api_key=f"{agent.id}.{api_secret}",
            kafka_username=kafka_username(command.tenant_id),
            kafka_password=kafka_password,
            kafka_topic=f"leads.{command.tenant_id}",
        )
