from abc import ABC, abstractmethod

from application.dtos.auth import LoginResult, OAuthChallengeResult
from domain.sessions.auth_challenge import AuthChallenge


class OAuthChallengeInputPort(ABC):
    @abstractmethod
    def start(self, provider: str, return_path: str) -> OAuthChallengeResult: ...

    @abstractmethod
    def consume(self, nonce: str | None, provider: str, state: str | None) -> AuthChallenge: ...


class SocialLoginInputPort(ABC):
    @abstractmethod
    def execute(
        self, provider: str, provider_subject: str, email: str | None, email_verified: bool
    ) -> LoginResult:
        """Resolve an already exchanged OAuth identity; every failure is InvalidCredentialsException."""
