from datetime import datetime, timezone
from uuid import uuid4

from application.dtos.auth import LoginResult
from application.ports.input.oauth import SocialLoginInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import PrimaryAuthentication
from application.use_cases.oauth.oauth_challenge import OAUTH_PROVIDERS
from domain.agents.agent import normalize_email
from domain.exceptions import DomainException, InvalidCredentialsException
from domain.social.social_identity import SocialIdentity


class SocialLoginUseCase(SocialLoginInputPort):
    """Resolve an already exchanged OAuth identity without keeping its HTTP call open."""

    def __init__(self, uow: UnitOfWorkPort, session_hours: int) -> None:
        self.uow = uow
        self.primary_authentication = PrimaryAuthentication(uow, session_hours)

    def execute(
        self, provider: str, provider_subject: str, email: str | None, email_verified: bool
    ) -> LoginResult:
        now = datetime.now(timezone.utc)
        if provider not in OAUTH_PROVIDERS or not provider_subject.strip():
            raise InvalidCredentialsException()
        try:
            with self.uow:
                identity = self.uow.social_identities.get_by_provider_subject(provider, provider_subject)
                if identity:
                    agent = self.uow.agents.get_by_id(identity.agent_id)
                    if not self.primary_authentication.eligible(agent) or not self.uow.social_identities.touch_last_login(identity.id, now):
                        raise InvalidCredentialsException()
                    return self.primary_authentication.authenticate(agent, now)

                # First login with this subject: link it only through a verified email.
                normalized_email = normalize_email(email or "")
                agent = self.uow.agents.get_by_email(normalized_email) if email_verified and normalized_email else None
                if not self.primary_authentication.eligible(agent):
                    raise InvalidCredentialsException()
                identity = SocialIdentity(
                    id=uuid4(), agent_id=agent.id.value, provider=provider,
                    provider_subject=provider_subject, email_at_link=normalized_email,
                    created_at=now, last_login_at=now,
                )
                if not self.uow.social_identities.save(identity):
                    raise InvalidCredentialsException()
                return self.primary_authentication.authenticate(agent, now)
        except DomainException as error:
            # Any other domain failure reads the same as a bad login, so nothing leaks.
            if isinstance(error, InvalidCredentialsException):
                raise
            raise InvalidCredentialsException() from None
