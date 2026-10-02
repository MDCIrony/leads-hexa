from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.jobs import GetIntakeJobsQuery, IntakeJobsPageResult
from domain.jobs.intake_job import IntakeJob


class GetIntakeJobsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetIntakeJobsQuery) -> IntakeJobsPageResult: ...


class GetIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> IntakeJob: ...


class ReprocessIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> None: ...
