from fastapi import Depends

from application.ports.input.advisors.advisor_use_case_ports import ListAdvisorsInputPort, SetAdvisorGroupInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.advisors.advisor_use_cases import ListAdvisorsUseCase, SetAdvisorGroupUseCase
from infrastructure.adapters.input.api.dependencies import get_container, get_uow
from infrastructure.di.container import Container


def get_list_advisors_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> ListAdvisorsInputPort:
    return ListAdvisorsUseCase(uow=uow)


def get_set_advisor_group_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), container: Container = Depends(get_container),
) -> SetAdvisorGroupInputPort:
    return SetAdvisorGroupUseCase(uow=uow, directory=container.advisor_directory)
