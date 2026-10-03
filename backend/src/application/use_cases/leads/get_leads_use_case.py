from application.dtos.leads import GetLeadsQuery, LeadsPageResult
from application.ports.input.leads.get_leads_use_case_port import GetLeadsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadStatus

class GetLeadsUseCase(GetLeadsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetLeadsQuery) -> LeadsPageResult:
        status = None
        if query.status is not None:
            try:
                status = LeadStatus(query.status)
            except ValueError:
                raise DomainException(
                    f"Unknown lead status: {query.status}",
                    error_code="INVALID_LEAD_STATUS",
                )
        with self.uow:
            items = self.uow.leads.list_by_tenant(
                tenant_id=query.tenant_id,
                status=status,
                assigned_agent_id=query.assigned_agent_id,
                group_id=query.group_id,
                source_id=query.source_id,
                search=query.search,
                updated_since=query.updated_since,
                limit=query.limit,
                offset=query.offset,
            )
            total = self.uow.leads.count_by_tenant(
                query.tenant_id,
                status=status,
                assigned_agent_id=query.assigned_agent_id,
                group_id=query.group_id,
                source_id=query.source_id,
                search=query.search,
                updated_since=query.updated_since,
            )
        return LeadsPageResult(items=items, total=total)
