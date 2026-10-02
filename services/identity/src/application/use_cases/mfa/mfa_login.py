from datetime import datetime, timezone

from application.dtos.auth import LoginResult
from application.ports.input.mfa import MfaLoginInputPort
from application.ports.output.mfa import MfaCryptoPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import (
    MFA_CHALLENGE_ATTEMPTS,
    MFA_CHALLENGE_PURPOSE,
    PrimaryAuthentication,
    new_session,
    token_hash,
)
from application.use_cases.mfa.factors import claim_factor
from domain.exceptions import InvalidMfaFactorException


class _LostMfaChallenge(Exception):
    """The factor was claimed but a concurrent request consumed the challenge first."""


class MfaLoginUseCase(MfaLoginInputPort):
    """Completes a password or social login that answered MFA_REQUIRED."""

    def __init__(self, uow: UnitOfWorkPort, crypto: MfaCryptoPort, session_hours: int = 8) -> None:
        self.uow = uow
        self.crypto = crypto
        self.session_hours = session_hours

    def verify_login(self, challenge_token: str | None, code: str) -> LoginResult:
        now = datetime.now(timezone.utc)
        if not challenge_token:
            raise InvalidMfaFactorException(terminal=True)
        challenge_hash = token_hash(challenge_token)
        session_token = None
        terminal = True
        try:
            with self.uow:
                # The attempt is counted before the code is checked, so a burst of
                # guesses cannot outrun the limit.
                if self.uow.challenges.reserve_attempt(challenge_hash, MFA_CHALLENGE_PURPOSE, now, MFA_CHALLENGE_ATTEMPTS):
                    challenge = self.uow.challenges.resolve_active(challenge_hash, now)
                    if challenge and challenge.agent_id:
                        terminal = challenge.attempts >= MFA_CHALLENGE_ATTEMPTS
                        agent = self.uow.agents.get_by_id(challenge.agent_id)
                        enrollment = self.uow.mfa.get(challenge.agent_id)
                        if (
                            PrimaryAuthentication.eligible(agent)
                            and enrollment and enrollment.enabled_at
                            and claim_factor(self.uow, self.crypto, enrollment, code, now)
                        ):
                            if not self.uow.challenges.consume(challenge_hash, now):
                                raise _LostMfaChallenge()
                            session_token, session = new_session(challenge.agent_id, now, self.session_hours)
                            self.uow.sessions.save(session)
        except _LostMfaChallenge:
            raise InvalidMfaFactorException(terminal=True) from None
        if session_token is None:
            raise InvalidMfaFactorException(terminal=terminal)
        return LoginResult(status="AUTHENTICATED", token=session_token)
