"""What handling an `intake.jobs` message means."""
import logging
from typing import Literal
from uuid import UUID

from chassis.web import request_id_var

from application.use_cases.jobs.manage_jobs import GetIntakeJobUseCase
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind
from infrastructure.di import use_cases

_LOGGER = logging.getLogger(__name__)


def process_job_message(container, message: dict) -> Literal["ack", "nack"]:
    """Parses the stored file of a batch, then processes the job's PENDING records.

    "nack" means a record stayed PENDING (lead-core unreachable, or a record
    raised): redelivering is what finishes the job, and the queue's delivery
    limit bounds how often."""
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
        if GetIntakeJobUseCase(uow).execute(tenant_id, job_id).kind == IntakeJobKind.BATCH:
            use_cases.process_batch(uow, container).execute(tenant_id, job_id)
        interrupted = use_cases.process_intake_job(uow, container).execute(tenant_id, job_id)
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
