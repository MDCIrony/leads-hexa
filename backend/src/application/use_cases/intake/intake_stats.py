from uuid import UUID

from application.dtos.intake_stats import IntakeStatsResult
from application.ports.input.intake.intake_stats_port import GetIntakeStatsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.value_objects.enums import IntakeRecordStatus


class GetIntakeStatsUseCase(GetIntakeStatsInputPort):
    """The inbox's counters, from intake's own records: after the cut lead-core cannot read them."""

    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID) -> IntakeStatsResult:
        with self.uow:
            pending = self.uow.intake_records.count_by_tenant(tenant_id, status=IntakeRecordStatus.PENDING)
            rejected = self.uow.intake_records.count_by_tenant(tenant_id, status=IntakeRecordStatus.REJECTED)
        return IntakeStatsResult(pending=pending, rejected=rejected, pending_intake=pending + rejected)
