from application.dtos.queries import GetLeadsQuery
from application.dtos.commands import LeadsPageResult
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort

class GetLeadsUseCase(GetLeadsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetLeadsQuery) -> LeadsPageResult:
        with self.uow:
            items = self.uow.leads.list_by_tenant(
                tenant_id=query.tenant_id,
                limit=query.limit,
                offset=query.offset,
            )
            total = self.uow.leads.count_by_tenant(query.tenant_id)
        return LeadsPageResult(items=items, total=total)
