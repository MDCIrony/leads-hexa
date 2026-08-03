from typing import List
from application.dtos.queries import GetLeadsQuery
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.lead import Lead

class GetLeadsUseCase(GetLeadsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetLeadsQuery) -> List[Lead]:
        with self.uow:
            return self.uow.leads.list_by_tenant(
                tenant_id=query.tenant_id,
                limit=query.limit,
                offset=query.offset
            )
