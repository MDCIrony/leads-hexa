from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import normalize_email
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole


class LoginUseCase(LoginInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.token_service = token_service

    def execute(self, email: str, password: str) -> str:
        with self.uow:
            agent = self.uow.agents.get_by_email(normalize_email(email))

        # One exception for every failure path: a caller must not be able to
        # tell an unknown account from a wrong password. INTEGRATION is
        # excluded here too: it is a machine principal whose only door in is
        # POST /agents/integration-credential, never a JWT session (ADR-0028).
        if (
            not agent
            or not agent.is_active
            or not agent.hashed_password
            or agent.role == AgentRole.INTEGRATION
        ):
            raise InvalidCredentialsException()
        if not self.password_hasher.verify(password, agent.hashed_password):
            raise InvalidCredentialsException()

        return self.token_service.issue(
            TokenClaims(
                agent_id=str(agent.id),
                role=agent.role.value,
                tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
            )
        )
