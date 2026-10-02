from fastapi import Depends
from pydantic import BaseModel

from application.ports.input.intake.intake_stats_port import GetIntakeStatsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.intake.intake_stats import GetIntakeStatsUseCase
from infrastructure.adapters.input.api.dependencies import get_uow


class IntakeStatsResponse(BaseModel):
    pending: int
    rejected: int
    pending_intake: int


def get_get_intake_stats_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeStatsInputPort:
    return GetIntakeStatsUseCase(uow=uow)
