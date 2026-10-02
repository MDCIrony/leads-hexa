from domain.events.intake_events import IntakeJobRequested, IntakeRejected


def test_a_requested_job_carries_only_the_fact_and_is_keyed_by_the_job():
    event = IntakeJobRequested(tenant_id="t-1", job_id="j-1")

    # event_id and occurred_on travel in the outbox envelope, not in the payload.
    assert event.as_payload() == {"tenant_id": "t-1", "job_id": "j-1"}
    assert event.partition_key == "j-1"
    assert event.event_type == "IntakeJobRequested"


def test_a_rejection_is_keyed_by_the_record_so_its_history_stays_ordered():
    event = IntakeRejected(tenant_id="t-1", intake_record_id="r-1", reason="INVALID_BUDGET")

    assert event.as_payload() == {"tenant_id": "t-1", "intake_record_id": "r-1", "reason": "INVALID_BUDGET"}
    assert event.partition_key == "r-1"
