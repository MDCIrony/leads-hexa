from abc import ABC, abstractmethod

from application.dtos.auth import CurrentIdentityResult, IntrospectionResult, LoginResult
from domain.agents.agent import Agent


class LoginInputPort(ABC):
    @abstractmethod
    def execute(self, email: str, password: str) -> LoginResult: ...


class LogoutInputPort(ABC):
    @abstractmethod
    def execute(self, session_token: str | None) -> None:
        """Revoke the session if there is one; logging out twice is not an error."""


class CurrentIdentityInputPort(ABC):
    @abstractmethod
    def execute(self, agent: Agent) -> CurrentIdentityResult: ...


class IntrospectInputPort(ABC):
    @abstractmethod
    def execute(
        self, api_key: str | None, session_token: str | None, optional: bool = False
    ) -> IntrospectionResult | None:
        """The API key wins over the session; a credential that is present but invalid
        raises UnauthorizedException even when optional. None only when optional and
        neither credential was presented."""
