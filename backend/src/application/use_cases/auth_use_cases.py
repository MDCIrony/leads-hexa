from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import InvalidCredentialsException
from infrastructure.security.password_hasher import verify_password
from infrastructure.security.jwt_service import create_access_token


class LoginUseCase(LoginInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, email: str, password: str) -> str:
        with self.uow:
            agent = self.uow.agents.get_by_email(email)

        if not agent or not agent.is_active or not agent.hashed_password:
            raise InvalidCredentialsException()
        if not verify_password(password, agent.hashed_password):
            raise InvalidCredentialsException()

        return create_access_token(
            agent_id=str(agent.id),
            role=agent.role.value,
            tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
        )
