from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import IntakeJobsPageResult
from application.dtos.queries import GetIntakeJobsQuery
from domain.entities.intake_job import IntakeJob


class GetIntakeJobsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetIntakeJobsQuery) -> IntakeJobsPageResult:
        pass


class GetIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> IntakeJob:
        pass


class ReprocessIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        pass
