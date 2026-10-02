from fastapi import APIRouter, Depends, File, UploadFile, status
from starlette.concurrency import run_in_threadpool

from application.dtos.context import RequestContext
from application.dtos.reception import ReceiveIntakeCommand
from application.ports.input.reception import ReceiveIntakeInputPort
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.intake.schemas import IngestLeadRequest, IntakeAcceptedResponse
from infrastructure.adapters.input.api.use_case_factories import get_receive_intake_use_case

router = APIRouter()

# The gateway's limit too, repeated because the service must hold it on its own.
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/leads/ingest", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_lead(
    request: IngestLeadRequest,
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
):
    # Reception records the job in the outbox in the same transaction as the
    # record; the relay hands it to RabbitMQ, so a broker outage only delays it.
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[request.model_dump()],
    ))
    return IntakeAcceptedResponse(job_id=received.job_id, record_ids=received.record_ids, status=received.status)


@router.post("/leads/batch-upload", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def batch_upload(
    file: UploadFile = File(...),
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
):
    # One byte past the limit is enough to know, without reading the rest.
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise DomainException("Request body too large", error_code="PAYLOAD_TOO_LARGE")
    # Stored with the job, since the file must outlive this process, and off the
    # event loop: up to 10 MB of bytea is a blocking write.
    received = await run_in_threadpool(receive.execute, ReceiveIntakeCommand(
        tenant_id=context.tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[],
        filename=file.filename, content=content,
    ))
    return IntakeAcceptedResponse(job_id=received.job_id, record_ids=[], status=received.status)
