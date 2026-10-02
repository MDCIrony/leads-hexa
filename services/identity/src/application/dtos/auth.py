from dataclasses import dataclass
from typing import Literal

from domain.agents.agent import Agent


@dataclass(frozen=True)
class LoginResult:
    """status AUTHENTICATED carries a session token; MFA_REQUIRED a challenge token."""

    status: Literal["AUTHENTICATED", "MFA_REQUIRED"]
    token: str


@dataclass(frozen=True)
class MfaSetupResult:
    secret: str
    otpauth_uri: str


@dataclass(frozen=True)
class OAuthChallengeResult:
    nonce: str
    state: str
    pkce_verifier: str
    return_path: str


@dataclass(frozen=True)
class IntrospectionResult:
    agent: Agent
    principal_type: Literal["human", "integration"]


@dataclass(frozen=True)
class CurrentIdentityResult:
    """What /auth/me shows the signed-in person about themselves."""

    agent: Agent
    tenant_name: str | None
    mfa_enabled: bool
    linked_oauth_providers: list[str]
