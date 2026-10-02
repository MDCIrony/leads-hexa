import logging

from chassis.outbox import OutboxRow

_LOGGER = logging.getLogger(__name__)


def job_message(row: OutboxRow) -> dict:
    """The `intake.jobs` payload for an outbox row; shared by the relay and the test gateway."""
    _LOGGER.info("Publishing intake job %s", row.payload["job_id"])
    return {
        "message_id": str(row.id),
        "schema_version": 1,
        "tenant_id": row.payload["tenant_id"],
        "job_id": row.payload["job_id"],
        "correlation_id": row.correlation_id,
    }
