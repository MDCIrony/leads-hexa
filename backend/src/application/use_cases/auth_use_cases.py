from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from domain.entities.auth_session import AuthSession
from domain.entities.agent import normalize_email
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole


class LoginUseCase(LoginInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        session_hours: int = 8,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.session_hours = session_hours

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

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        with self.uow:
            self.uow.sessions.save(AuthSession(
                token_hash=sha256(token.encode()).hexdigest(),
                agent_id=agent.id.value,
                created_at=now,
                expires_at=now + timedelta(hours=self.session_hours),
            ))
        return token
