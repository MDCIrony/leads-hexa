from fastapi import APIRouter, Depends, status

from application.dtos.context import RequestContext
from application.ports.input.records import GetIntakeStatsInputPort
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.intake.schemas import IntakeStatsResponse
from infrastructure.adapters.input.api.use_case_factories import get_get_intake_stats_use_case

router = APIRouter()


@router.get("/stats", response_model=IntakeStatsResponse, status_code=status.HTTP_200_OK)
def get_intake_stats(
    # Manager-only like the rest of the inbox: it counts the organization's records.
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeStatsInputPort = Depends(get_get_intake_stats_use_case),
):
    result = use_case.execute(context.tenant_id)
    return IntakeStatsResponse(pending=result.pending, rejected=result.rejected, pending_intake=result.pending_intake)
