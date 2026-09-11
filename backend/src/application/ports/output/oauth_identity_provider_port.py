import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class OAuthIdentity:
    provider_subject: str
    email: str | None
    email_verified: bool
    name: str | None


class OAuthIdentityProviderError(Exception):
    """An external OAuth response cannot establish an application identity."""


class OAuthIdentityProviderPort(abc.ABC):
    @abc.abstractmethod
    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity: ...
