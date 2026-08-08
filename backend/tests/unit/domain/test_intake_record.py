import pytest

from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeRecordStatus

TENANT_ID = "11111111-1111-1111-1111-111111111111"
SOURCE_ID = "22222222-2222-2222-2222-222222222222"
LEAD_ID = "33333333-3333-3333-3333-333333333333"


def _record(status: IntakeRecordStatus = IntakeRecordStatus.PENDING) -> IntakeRecord:
    return IntakeRecord.create(
        tenant_id=TENANT_ID,
        source_id=SOURCE_ID,
        payload={"email": "lead@example.com"},
        status=status,
    )


# --- promote ---


@pytest.mark.parametrize("status", [IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED])
def test_promote_succeeds_from_pending_or_rejected(status):
    record = _record(status)

    record.promote(LEAD_ID)

    assert record.status == IntakeRecordStatus.PROMOTED
    assert str(record.lead_id) == LEAD_ID
    assert record.processed_at is not None


@pytest.mark.parametrize("status", [IntakeRecordStatus.PROMOTED, IntakeRecordStatus.DISCARDED])
def test_promote_fails_from_a_terminal_status(status):
    record = _record(status)

    with pytest.raises(DomainException) as exc_info:
        record.promote(LEAD_ID)

    assert exc_info.value.error_code == "INVALID_INTAKE_TRANSITION"


# --- reject ---


def test_reject_succeeds_from_pending():
    record = _record(IntakeRecordStatus.PENDING)

    record.reject([IntakeError(field="email", message="Invalid format")])

    assert record.status == IntakeRecordStatus.REJECTED
    assert len(record.errors) == 1
    assert record.processed_at is not None


def test_reject_from_rejected_replaces_errors_and_stays_rejected():
    record = _record(IntakeRecordStatus.PENDING)
    record.reject([IntakeError(field="email", message="Invalid format")])

    record.reject([IntakeError(field="budget", message="Must be positive")])

    assert record.status == IntakeRecordStatus.REJECTED
    assert len(record.errors) == 1
    assert record.errors[0].field == "budget"


@pytest.mark.parametrize("status", [IntakeRecordStatus.PROMOTED, IntakeRecordStatus.DISCARDED])
def test_reject_fails_from_a_terminal_status(status):
    record = _record(status)

    with pytest.raises(DomainException) as exc_info:
        record.reject([IntakeError(field="email", message="Invalid format")])

    assert exc_info.value.error_code == "INVALID_INTAKE_TRANSITION"


def test_reject_without_errors_is_rejected():
    record = _record(IntakeRecordStatus.PENDING)

    with pytest.raises(DomainException) as exc_info:
        record.reject([])

    assert exc_info.value.error_code == "REJECTION_WITHOUT_ERRORS"


# --- discard ---


@pytest.mark.parametrize("status", [IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED])
def test_discard_succeeds_from_pending_or_rejected(status):
    record = _record(status)

    record.discard()

    assert record.status == IntakeRecordStatus.DISCARDED
    assert record.processed_at is not None


@pytest.mark.parametrize("status", [IntakeRecordStatus.PROMOTED, IntakeRecordStatus.DISCARDED])
def test_discard_fails_from_a_terminal_status(status):
    record = _record(status)

    with pytest.raises(DomainException) as exc_info:
        record.discard()

    assert exc_info.value.error_code == "INVALID_INTAKE_TRANSITION"
