from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from application.ports.output.consumers import ProcessedEventRepositoryPort
from application.ports.output.files import IntakeFileRepositoryPort
from application.ports.output.jobs import IntakeJobRepositoryPort
from application.ports.output.outbox import OutboxRepositoryPort
from application.ports.output.records import IntakeRecordRepositoryPort
from application.ports.output.sources import LeadSourceRepositoryPort
from application.ports.output.tenants import ProvisionedTenantRepositoryPort


class UnitOfWorkPort(ABC):
    sources: LeadSourceRepositoryPort
    intake_jobs: IntakeJobRepositoryPort
    intake_records: IntakeRecordRepositoryPort
    intake_files: IntakeFileRepositoryPort
    outbox: OutboxRepositoryPort
    processed_events: ProcessedEventRepositoryPort
    provisioned_tenants: ProvisionedTenantRepositoryPort

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
