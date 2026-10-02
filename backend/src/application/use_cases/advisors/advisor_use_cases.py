from application.dtos.advisors import AdvisorsPage, AdvisorView, ListAdvisorsQuery, SetAdvisorGroupCommand
from application.ports.input.advisors.advisor_use_case_ports import ListAdvisorsInputPort, SetAdvisorGroupInputPort
from application.ports.output.advisors.advisor_directory_port import AdvisorDirectoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.sales_group_use_cases import get_owned_group
from domain.exceptions import DomainException


class ListAdvisorsUseCase(ListAdvisorsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: ListAdvisorsQuery) -> AdvisorsPage:
        with self.uow:
            advisors = self.uow.advisors.list(query.tenant_id, query.group_id, query.is_active,
                                              query.limit, query.offset)
            total = self.uow.advisors.count(query.tenant_id, query.group_id, query.is_active)
            loads = self.uow.leads.active_load_by_agent(query.tenant_id)
        return AdvisorsPage([AdvisorView(a, loads.get(a.agent_id.value, 0)) for a in advisors], total)


class SetAdvisorGroupUseCase(SetAdvisorGroupInputPort):
    def __init__(self, uow: UnitOfWorkPort, directory: AdvisorDirectoryPort) -> None:
        self.uow = uow
        self.directory = directory

    def execute(self, command: SetAdvisorGroupCommand) -> AdvisorView:
        # Before the transaction: hydrating commits on a connection of its own,
        # and holding this one meanwhile would take two from the pool per request.
        self.directory.get(command.agent_id, command.tenant_id)
        with self.uow:
            if command.group_id is not None:
                get_owned_group(self.uow, command.tenant_id, command.group_id)
            if not self.uow.advisors.set_group(command.agent_id, command.tenant_id, command.group_id):
                # Resolved a moment ago, gone now: say so instead of failing on a missing row.
                raise DomainException("El asesor no existe", error_code="AGENT_NOT_FOUND")
            advisor = self.uow.advisors.get(command.agent_id, command.tenant_id)
            load = self.uow.leads.active_load_by_agent(command.tenant_id).get(command.agent_id, 0)
        return AdvisorView(advisor, load)
