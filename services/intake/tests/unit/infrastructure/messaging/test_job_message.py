import uuid
from datetime import datetime, timezone

from chassis.outbox import OutboxRow
from chassis.testing.contracts import assert_conforms

from infrastructure.adapters.output.queue.job_message import job_message
from infrastructure.adapters.output.queue.topology import DLQ_NAME, QUEUE_NAME, declare_intake_topology


def _row(correlation_id):
    return OutboxRow(
        id=uuid.uuid4(), channel="job", tenant_id=str(uuid.uuid4()), partition_key="j",
        event_type="IntakeJobRequested", payload={"tenant_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())},
        occurred_on=datetime.now(timezone.utc), correlation_id=correlation_id,
    )


def test_the_message_carries_its_outbox_id_and_correlation_id_and_conforms_to_the_contract():
    row = _row("req-42")

    message = job_message(row)

    assert message == {
        "message_id": str(row.id), "schema_version": 1, "tenant_id": row.payload["tenant_id"],
        "job_id": row.payload["job_id"], "correlation_id": "req-42",
    }
    assert_conforms(message, "schemas/intake/job-message.v1.schema.json")


def test_a_job_without_a_correlation_id_still_conforms():
    assert_conforms(job_message(_row(None)), "schemas/intake/job-message.v1.schema.json")


def test_the_topology_is_a_quorum_queue_that_dead_letters_to_its_dlq():
    declared = []

    class _Channel:
        def queue_declare(self, queue, durable, arguments=None):
            declared.append((queue, durable, arguments))

    declare_intake_topology(_Channel())

    assert declared == [
        (DLQ_NAME, True, None),
        (QUEUE_NAME, True, {"x-queue-type": "quorum", "x-delivery-limit": 3,
                            "x-dead-letter-exchange": "", "x-dead-letter-routing-key": DLQ_NAME}),
    ]
    assert (QUEUE_NAME, DLQ_NAME) == ("intake.jobs", "intake.jobs.dlq")
