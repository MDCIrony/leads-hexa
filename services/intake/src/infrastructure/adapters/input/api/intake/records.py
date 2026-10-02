from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from application.dtos.context import RequestContext
from application.dtos.records import GetIntakeRecordsQuery, PromoteIntakeRecordCommand
from application.ports.input.records import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    PromoteIntakeRecordInputPort,
)
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.intake.schemas import (
    IntakeErrorResponse,
    IntakeRecordResponse,
    IntakeRecordsPageResponse,
    LeadProcessedResponse,
    PromoteIntakeRecordRequest,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_discard_intake_record_use_case,
    get_get_intake_records_use_case,
    get_promote_intake_record_use_case,
)

router = APIRouter()


def _to_record_response(record: IntakeRecord) -> IntakeRecordResponse:
    return IntakeRecordResponse(
        id=str(record.id),
        source_id=str(record.source_id),
        status=record.status.value,
        payload=record.payload,
        errors=[
            IntakeErrorResponse(
                field=error.field, message=error.message,
                received_value=error.received_value, error_code=error.error_code,
            )
            for error in record.errors
        ],
        received_at=record.received_at,
        processed_at=record.processed_at,
        lead_id=str(record.lead_id) if record.lead_id else None,
    )


@router.get("/records", response_model=IntakeRecordsPageResponse, status_code=status.HTTP_200_OK)
def list_intake_records(
    status: Optional[str] = None,
    job_id: Optional[UUID] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeRecordsInputPort = Depends(get_get_intake_records_use_case),
):
    page = use_case.execute(GetIntakeRecordsQuery(
        tenant_id=context.tenant_id, status=status, job_id=job_id, limit=limit, offset=offset,
    ))
    items = [_to_record_response(record) for record in page.items]
    return IntakeRecordsPageResponse(
        items=items, total=page.total, limit=limit, offset=offset, has_more=(offset + len(items)) < page.total,
    )


@router.post("/records/{record_id}/promote", response_model=LeadProcessedResponse, status_code=status.HTTP_200_OK)
def promote_intake_record(
    record_id: UUID,
    request: PromoteIntakeRecordRequest,
    context: RequestContext = Depends(require_organization_manager),
    use_case: PromoteIntakeRecordInputPort = Depends(get_promote_intake_record_use_case),
):
    result = use_case.execute(PromoteIntakeRecordCommand(
        tenant_id=context.tenant_id, record_id=record_id, payload=request.payload,
    ))
    if result.status == IntakeRecordStatus.REJECTED.value:
        # A retry that fails again is a bad request, not a 200. Nothing is lost
        # either way: the ingestion already re-saved the record as REJECTED
        # with its new errors before returning.
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "error_code": result.error_code,
                "message": result.error,
                "intake_record_id": result.intake_record_id,
            },
        )
    return LeadProcessedResponse(
        lead_id=result.lead_id,
        status=result.status,
        score=result.score,
        assigned_agent_id=result.assigned_agent_id,
        applied_rules_count=result.applied_rules_count,
        error=result.error,
        error_code=result.error_code,
        intake_record_id=result.intake_record_id,
    )


@router.post("/records/{record_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard_intake_record(
    record_id: UUID,
    context: RequestContext = Depends(require_organization_manager),
    use_case: DiscardIntakeRecordInputPort = Depends(get_discard_intake_record_use_case),
):
    use_case.execute(tenant_id=context.tenant_id, record_id=record_id)
