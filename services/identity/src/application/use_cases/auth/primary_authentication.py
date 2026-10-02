import secrets
from datetime import datetime, timedelta
from hashlib import sha256

from application.dtos.auth import LoginResult
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.agents.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.sessions.auth_challenge import AuthChallenge
from domain.sessions.auth_session import AuthSession
from domain.value_objects.agent_role import AgentRole

MFA_CHALLENGE_PURPOSE = "MFA_LOGIN"
MFA_CHALLENGE_MINUTES = 5
MFA_CHALLENGE_ATTEMPTS = 5


def token_hash(token: str) -> str:
    """Sessions, challenges and recovery codes are stored only as this hash."""
    return sha256(token.encode()).hexdigest()


def new_session(agent_id, now: datetime, session_hours: int) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    return token, AuthSession(
        token_hash=token_hash(token), agent_id=agent_id,
        created_at=now, expires_at=now + timedelta(hours=session_hours),
    )


class PrimaryAuthentication:
    """The shared session-or-MFA decision, applied once a first factor is verified."""

    def __init__(self, uow: UnitOfWorkPort, session_hours: int) -> None:
        self.uow = uow
        self.session_hours = session_hours

    @staticmethod
    def eligible(agent: Agent | None) -> bool:
        # INTEGRATION is a machine principal: its only door in is the API key.
        return bool(agent and agent.is_active and agent.role != AgentRole.INTEGRATION)

    def authenticate(self, agent: Agent, now: datetime) -> LoginResult:
        if not self.eligible(agent):
            raise InvalidCredentialsException()
        enrollment = self.uow.mfa.get(agent.id.value)
        # A fresh login replaces any live challenge but inherits its attempts and
        # deadline, or re-logging in would reset the MFA attempt limit.
        previous = self.uow.challenges.invalidate_active_for_agent(
            agent.id.value, MFA_CHALLENGE_PURPOSE, now
        )
        if enrollment and enrollment.enabled_at is not None:
            token = secrets.token_urlsafe(32)
            self.uow.challenges.save(AuthChallenge(
                token_hash=token_hash(token), agent_id=agent.id.value, purpose=MFA_CHALLENGE_PURPOSE,
                attempts=previous.attempts if previous else 0,
                expires_at=previous.expires_at if previous else now + timedelta(minutes=MFA_CHALLENGE_MINUTES),
                consumed_at=None, created_at=now,
            ))
            return LoginResult(status="MFA_REQUIRED", token=token)
        token, session = new_session(agent.id.value, now, self.session_hours)
        self.uow.sessions.save(session)
        return LoginResult(status="AUTHENTICATED", token=token)
