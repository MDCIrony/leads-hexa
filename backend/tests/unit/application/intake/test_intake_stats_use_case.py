import uuid

from application.use_cases.intake.intake_stats import GetIntakeStatsUseCase
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _record(uow, tenant_id, status):
    uow.intake_records.save(IntakeRecord.create(tenant_id=tenant_id, source_id=uuid.uuid4(), payload={},
                                                status=status))


def test_pending_intake_is_what_still_needs_someone_pending_plus_rejected():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()
    for status in (IntakeRecordStatus.PENDING, IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED,
                   IntakeRecordStatus.PROMOTED, IntakeRecordStatus.DISCARDED):
        _record(uow, tenant_id, status)
    _record(uow, uuid.uuid4(), IntakeRecordStatus.PENDING)

    stats = GetIntakeStatsUseCase(uow).execute(tenant_id)

    assert (stats.pending, stats.rejected, stats.pending_intake) == (2, 1, 3)
