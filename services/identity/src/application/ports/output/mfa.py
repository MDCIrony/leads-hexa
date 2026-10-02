from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from domain.mfa.agent_mfa import AgentMfa


class AgentMfaRepositoryPort(ABC):
    @abstractmethod
    def get(self, agent_id: UUID) -> AgentMfa | None: ...

    @abstractmethod
    def save_pending(self, enrollment: AgentMfa) -> None: ...

    @abstractmethod
    def confirm(self, agent_id: UUID, step: int, now: datetime) -> bool: ...

    @abstractmethod
    def claim_totp_step(self, agent_id: UUID, step: int) -> bool:
        """True only when step is newer than the last one used: a TOTP code works once."""

    @abstractmethod
    def replace_recovery_codes(self, agent_id: UUID, code_hashes: Iterable[str], now: datetime) -> None: ...

    @abstractmethod
    def consume_recovery_code(self, agent_id: UUID, code_hash: str, now: datetime) -> bool: ...

    @abstractmethod
    def delete(self, agent_id: UUID) -> None:
        """Drop the enrollment and its recovery codes."""


class MfaCryptoPort(ABC):
    @abstractmethod
    def generate_secret(self) -> str: ...

    @abstractmethod
    def encrypt(self, secret: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...

    @abstractmethod
    def matching_step(self, secret: str, code: str, now: datetime) -> int | None:
        """The TOTP step code belongs to, inside the accepted window, or None."""

    @abstractmethod
    def provisioning_uri(self, secret: str, email: str) -> str: ...
