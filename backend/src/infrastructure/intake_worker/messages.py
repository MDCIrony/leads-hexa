"""What an `intake.jobs` message is, and what handling one means.

Shared by the relay that publishes it, the intake worker that consumes it and
the test gateway that does both in process, so the three cannot drift apart."""
import logging
from typing import Literal
from uuid import UUID

from chassis.outbox import OutboxRow
from chassis.web import request_id_var

from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind
from infrastructure.adapters.input.api.dependencies import (
    get_get_intake_job_use_case,
    get_ingest_lead_use_case,
    get_process_batch_use_case,
    get_process_intake_job_use_case,
)

_LOGGER = logging.getLogger(__name__)


def job_message(row: OutboxRow) -> dict:
    _LOGGER.info("Publishing intake job %s", row.payload["job_id"])
    return {
        "message_id": str(row.id),
        "schema_version": 1,
        "tenant_id": row.payload["tenant_id"],
        "job_id": row.payload["job_id"],
        "correlation_id": row.correlation_id,
    }


def process_job_message(container, message: dict) -> Literal["ack", "nack"]:
    """Parses the stored file of a batch, then processes the job's PENDING records.

    "nack" means a record raised and stayed PENDING: redelivering is what
    finishes the job, and the queue's delivery limit bounds how often."""
    correlation_id = message.get("correlation_id")
    token = request_id_var.set(correlation_id) if correlation_id else None
    try:
        return _process(container, UUID(message["tenant_id"]), UUID(message["job_id"]))
    finally:
        if token is not None:
            request_id_var.reset(token)


def _process(container, tenant_id: UUID, job_id: UUID) -> Literal["ack", "nack"]:
    _LOGGER.info("Processing intake job %s", job_id)
    # A fresh unit of work per message, same reasoning as one per HTTP request.
    uow = container.unit_of_work()
    try:
        if get_get_intake_job_use_case(uow=uow).execute(tenant_id, job_id).kind == IntakeJobKind.BATCH:
            get_process_batch_use_case(uow=uow, container=container).execute(tenant_id, job_id)
        ingest = get_ingest_lead_use_case(uow=uow, container=container)
        interrupted = get_process_intake_job_use_case(uow=uow, ingest=ingest).execute(tenant_id, job_id)
    except DomainException as exc:
        # A missing job, or a finished one (completed, or failed on an
        # unreadable file): redelivering cannot change either.
        _LOGGER.info("Intake job %s not processable (%s), acking", job_id, exc.error_code)
        return "ack"
    except Exception:
        _LOGGER.error("Failed processing intake job %s, requeueing", job_id, exc_info=True)
        return "nack"
    if interrupted:
        _LOGGER.warning("Intake job %s left records pending, requeueing", job_id)
        return "nack"
    _LOGGER.info("Intake job %s done", job_id)
    return "ack"
