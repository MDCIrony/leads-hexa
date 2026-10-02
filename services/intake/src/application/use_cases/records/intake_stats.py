from uuid import UUID

from application.dtos.records import IntakeStatsResult
from application.ports.input.records import GetIntakeStatsInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.value_objects.enums import IntakeRecordStatus


class GetIntakeStatsUseCase(GetIntakeStatsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID) -> IntakeStatsResult:
        # One transaction for both counts: the inbox badge is a single snapshot.
        with self.uow:
            pending = self.uow.intake_records.count_by_tenant(tenant_id, status=IntakeRecordStatus.PENDING)
            rejected = self.uow.intake_records.count_by_tenant(tenant_id, status=IntakeRecordStatus.REJECTED)
        return IntakeStatsResult(pending=pending, rejected=rejected, pending_intake=pending + rejected)
