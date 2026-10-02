import secrets
from datetime import datetime, timedelta, timezone

from application.dtos.auth import OAuthChallengeResult
from application.ports.input.oauth import OAuthChallengeInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import token_hash
from domain.exceptions import InvalidCredentialsException
from domain.sessions.auth_challenge import AuthChallenge

OAUTH_PROVIDERS = frozenset({"GOOGLE", "GITHUB"})
OAUTH_CHALLENGE_PURPOSE = "OAUTH_LOGIN"
OAUTH_CHALLENGE_MINUTES = 5


class OAuthChallengeUseCase(OAuthChallengeInputPort):
    """Persist and atomically consume the browser-bound OAuth proof."""

    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def start(self, provider: str, return_path: str) -> OAuthChallengeResult:
        if provider not in OAUTH_PROVIDERS or not AuthChallenge._internal_return_path(return_path):
            raise InvalidCredentialsException()
        now = datetime.now(timezone.utc)
        nonce = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        with self.uow:
            self.uow.challenges.save(AuthChallenge(
                token_hash=token_hash(nonce), agent_id=None, purpose=OAUTH_CHALLENGE_PURPOSE, attempts=0,
                expires_at=now + timedelta(minutes=OAUTH_CHALLENGE_MINUTES), consumed_at=None,
                created_at=now, provider=provider, state_hash=token_hash(state),
                pkce_verifier=verifier, return_path=return_path,
            ))
        return OAuthChallengeResult(nonce, state, verifier, return_path)

    def consume(self, nonce: str | None, provider: str, state: str | None) -> AuthChallenge:
        if not nonce or not state or provider not in OAUTH_PROVIDERS:
            raise InvalidCredentialsException()
        now = datetime.now(timezone.utc)
        with self.uow:
            challenge = self.uow.challenges.consume_oauth(token_hash(nonce), provider, token_hash(state), now)
        if challenge is None:
            raise InvalidCredentialsException()
        return challenge
