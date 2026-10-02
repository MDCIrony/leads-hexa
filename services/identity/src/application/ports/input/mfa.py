from abc import ABC, abstractmethod

from application.dtos.auth import LoginResult, MfaSetupResult
from domain.agents.agent import Agent


class MfaEnrollmentInputPort(ABC):
    """The signed-in agent managing its own second factor."""

    @abstractmethod
    def setup(self, agent: Agent, password: str) -> MfaSetupResult: ...

    @abstractmethod
    def confirm(self, agent: Agent, current_session_token: str, code: str) -> list[str]:
        """Enable MFA; returns the plaintext recovery codes and revokes every other session."""

    @abstractmethod
    def regenerate_recovery_codes(self, agent: Agent, password: str, code: str) -> list[str]: ...

    @abstractmethod
    def disable(self, agent: Agent, current_session_token: str | None, password: str, code: str) -> None: ...


class MfaLoginInputPort(ABC):
    @abstractmethod
    def verify_login(self, challenge_token: str | None, code: str) -> LoginResult:
        """Raises InvalidMfaFactorException; its terminal flag says the challenge is spent."""
