from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from application.dtos.reception import StoredIntakeFile


class IntakeFileRepositoryPort(ABC):
    @abstractmethod
    def save(self, job_id: UUID, tenant_id: UUID, filename: str, content: bytes) -> None: ...

    @abstractmethod
    def get(self, job_id: UUID, tenant_id: UUID) -> Optional[StoredIntakeFile]:
        """None for a file of another organization, same as for a missing one."""

    @abstractmethod
    def mark_parsed(self, job_id: UUID) -> None: ...
