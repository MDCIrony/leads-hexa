from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.intake_stats import IntakeStatsResult


class GetIntakeStatsInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID) -> IntakeStatsResult:
        pass
