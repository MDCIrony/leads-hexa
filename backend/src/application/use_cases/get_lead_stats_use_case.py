from application.dtos.queries import GetLeadStatsQuery
from application.dtos.commands import AgentLoad, LeadStatsResult
from application.ports.input.get_lead_stats_use_case_port import GetLeadStatsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadStatus


class GetLeadStatsUseCase(GetLeadStatsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetLeadStatsQuery) -> LeadStatsResult:
        if (
            query.date_from is not None
            and query.date_to is not None
            and query.date_from > query.date_to
        ):
            raise DomainException(
                "'from' must not be later than 'to'", error_code="INVALID_DATE_RANGE"
            )

        # One transaction for both reads: a manager's panel is a single
        # snapshot, not two moments stitched together.
        with self.uow:
            by_status = self.uow.leads.count_by_status(
                query.tenant_id, date_from=query.date_from, date_to=query.date_to
            )
            load_rows = self.uow.leads.active_load_by_agent_with_names(query.tenant_id)

        return LeadStatsResult(
            total=sum(by_status.values()),
            by_status=by_status,
            unassigned=by_status[LeadStatus.UNASSIGNED.value],
            load_by_agent=[
                AgentLoad(agent_id=agent_id, name=name, active_leads=load)
                for agent_id, name, load in load_rows
            ],
        )
