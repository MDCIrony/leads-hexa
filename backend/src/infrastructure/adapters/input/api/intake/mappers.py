from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from infrastructure.adapters.input.api.schemas import IntakeErrorResponse, IntakeJobResponse, IntakeRecordResponse


def to_record_response(record: IntakeRecord) -> IntakeRecordResponse:
    return IntakeRecordResponse(
        id=str(record.id),
        source_id=str(record.source_id),
        status=record.status.value,
        payload=record.payload,
        errors=[
            IntakeErrorResponse(
                field=error.field,
                message=error.message,
                received_value=error.received_value,
                error_code=error.error_code,
            )
            for error in record.errors
        ],
        received_at=record.received_at,
        processed_at=record.processed_at,
        lead_id=str(record.lead_id) if record.lead_id else None,
    )


def to_job_response(job: IntakeJob) -> IntakeJobResponse:
    return IntakeJobResponse(
        id=str(job.id),
        source_id=str(job.source_id),
        kind=job.kind.value,
        status=job.status.value,
        total_items=job.total_items,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
