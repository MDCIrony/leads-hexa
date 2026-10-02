from uuid import uuid4

from application.use_cases.records.intake_stats import GetIntakeStatsUseCase
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _add(uow, tenant_id, status):
    uow.intake_records.save(IntakeRecord.create(tenant_id=tenant_id, source_id=uuid4(), payload={}, status=status))


def test_the_inbox_is_the_pending_and_the_rejected_records_of_the_organization_alone():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    for status in (IntakeRecordStatus.PENDING, IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED,
                   IntakeRecordStatus.PROMOTED, IntakeRecordStatus.DISCARDED):
        _add(uow, tenant_id, status)
    _add(uow, uuid4(), IntakeRecordStatus.PENDING)

    stats = GetIntakeStatsUseCase(uow).execute(tenant_id)

    assert (stats.pending, stats.rejected, stats.pending_intake) == (2, 1, 3)


def test_an_organization_with_no_records_has_an_empty_inbox():
    stats = GetIntakeStatsUseCase(InMemoryUnitOfWork()).execute(uuid4())

    assert (stats.pending, stats.rejected, stats.pending_intake) == (0, 0, 0)
