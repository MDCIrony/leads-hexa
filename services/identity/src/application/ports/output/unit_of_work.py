from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from application.ports.output.agents import AgentRepositoryPort
from application.ports.output.mfa import AgentMfaRepositoryPort
from application.ports.output.outbox import OutboxRepositoryPort
from application.ports.output.sessions import AuthChallengeRepositoryPort, AuthSessionRepositoryPort
from application.ports.output.social import SocialIdentityRepositoryPort
from application.ports.output.tenants import TenantRepositoryPort


class UnitOfWorkPort(ABC):
    agents: AgentRepositoryPort
    tenants: TenantRepositoryPort
    sessions: AuthSessionRepositoryPort
    challenges: AuthChallengeRepositoryPort
    mfa: AgentMfaRepositoryPort
    social_identities: SocialIdentityRepositoryPort
    outbox: OutboxRepositoryPort

    def __enter__(self) -> UnitOfWorkPort:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
