from datetime import datetime, timezone

from application.dtos.auth import LoginResult
from application.ports.input.auth import LoginInputPort
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import PrimaryAuthentication
from domain.agents.agent import normalize_email
from domain.exceptions import InvalidCredentialsException


class LoginUseCase(LoginInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort, session_hours: int = 8) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.primary_authentication = PrimaryAuthentication(uow, session_hours)

    def execute(self, email: str, password: str) -> LoginResult:
        now = datetime.now(timezone.utc)
        with self.uow:
            agent = self.uow.agents.get_by_email(normalize_email(email))
            # One exception for every failure path: a caller must not tell an
            # unknown account from a wrong password.
            if (
                not PrimaryAuthentication.eligible(agent)
                or not agent.hashed_password
                or not self.password_hasher.verify(password, agent.hashed_password)
            ):
                raise InvalidCredentialsException()
            return self.primary_authentication.authenticate(agent, now)
