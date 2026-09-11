import abc
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from domain.entities.agent_mfa import AgentMfa


class AgentMfaRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def get(self, agent_id: UUID) -> Optional[AgentMfa]: ...

    @abc.abstractmethod
    def save_pending(self, enrollment: AgentMfa) -> None: ...

    @abc.abstractmethod
    def confirm(self, agent_id: UUID, step: int, now: datetime) -> bool: ...

    @abc.abstractmethod
    def claim_totp_step(self, agent_id: UUID, step: int) -> bool: ...

    @abc.abstractmethod
    def replace_recovery_codes(self, agent_id: UUID, code_hashes: Iterable[str], now: datetime) -> None: ...

    @abc.abstractmethod
    def consume_recovery_code(self, agent_id: UUID, code_hash: str, now: datetime) -> bool: ...

    @abc.abstractmethod
    def delete(self, agent_id: UUID) -> None: ...
