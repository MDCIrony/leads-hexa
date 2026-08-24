import pytest

from domain.entities.intake_job import IntakeJob
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus

TENANT_ID = "11111111-1111-1111-1111-111111111111"
SOURCE_ID = "22222222-2222-2222-2222-222222222222"


def _job(status: IntakeJobStatus = IntakeJobStatus.PENDING) -> IntakeJob:
    job = IntakeJob.create(tenant_id=TENANT_ID, source_id=SOURCE_ID, kind=IntakeJobKind.SINGLE)
    job.status = status
    return job


# --- create ---


def test_create_starts_pending_with_zeroed_counters():
    job = IntakeJob.create(tenant_id=TENANT_ID, source_id=SOURCE_ID, kind=IntakeJobKind.BATCH)

    assert job.status == IntakeJobStatus.PENDING
    assert job.succeeded == 0
    assert job.failed == 0
    assert job.total_items is None


# --- start ---


def test_start_from_pending_moves_to_processing():
    job = _job(IntakeJobStatus.PENDING)

    job.start()

    assert job.status == IntakeJobStatus.PROCESSING


def test_start_from_processing_is_idempotent():
    """The state a worker that died mid-run leaves behind. A redelivered
    message finds the job already started, and refusing it would nack and
    redeliver forever instead of finishing the records still PENDING."""
    job = _job(IntakeJobStatus.PROCESSING)

    job.start()

    assert job.status == IntakeJobStatus.PROCESSING


@pytest.mark.parametrize("status", [IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED])
def test_start_fails_from_a_terminal_status(status):
    job = _job(status)

    with pytest.raises(DomainException) as exc_info:
        job.start()

    assert exc_info.value.error_code == "INVALID_JOB_TRANSITION"


# --- set_total ---


def test_set_total_from_processing_sets_it():
    job = _job(IntakeJobStatus.PROCESSING)

    job.set_total(42)

    assert job.total_items == 42


def test_set_total_twice_is_rejected():
    job = _job(IntakeJobStatus.PROCESSING)
    job.set_total(42)

    with pytest.raises(DomainException) as exc_info:
        job.set_total(7)

    assert exc_info.value.error_code == "INVALID_JOB_TRANSITION"


# --- set_counters ---


def test_set_counters_overwrites_without_changing_status():
    """Set, not incremented: a rerun of the same job must land on the count
    the records show, not on that count added to what it remembered."""
    job = _job(IntakeJobStatus.PROCESSING)
    job.set_counters(succeeded=2, failed=1)

    job.set_counters(succeeded=2, failed=1)

    assert job.succeeded == 2
    assert job.failed == 1
    assert job.status == IntakeJobStatus.PROCESSING


# --- complete / fail ---


def test_complete_seals_completed_at():
    job = _job(IntakeJobStatus.PROCESSING)

    job.complete()

    assert job.status == IntakeJobStatus.COMPLETED
    assert job.completed_at is not None


def test_fail_seals_completed_at():
    job = _job(IntakeJobStatus.PROCESSING)

    job.fail()

    assert job.status == IntakeJobStatus.FAILED
    assert job.completed_at is not None


@pytest.mark.parametrize("status", [IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED])
@pytest.mark.parametrize("method", ["complete", "fail", "reset_counters"])
def test_any_transition_from_a_terminal_status_is_rejected(method, status):
    job = _job(status)

    with pytest.raises(DomainException) as exc_info:
        getattr(job, method)()

    assert exc_info.value.error_code == "INVALID_JOB_TRANSITION"


# --- reset_counters ---


def test_reset_counters_on_processing_returns_to_pending_zeroed():
    job = _job(IntakeJobStatus.PROCESSING)
    job.set_counters(succeeded=1, failed=1)

    job.reset_counters()

    assert job.status == IntakeJobStatus.PENDING
    assert job.succeeded == 0
    assert job.failed == 0


def test_reset_counters_on_completed_is_rejected():
    job = _job(IntakeJobStatus.COMPLETED)

    with pytest.raises(DomainException) as exc_info:
        job.reset_counters()

    assert exc_info.value.error_code == "INVALID_JOB_TRANSITION"
