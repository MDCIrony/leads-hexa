from fastapi import Depends

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.ports.input.leads.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.leads.get_lead_stats_use_case_port import GetLeadStatsInputPort
from application.ports.input.rules.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, CreateScoringRuleInputPort, DeleteAssignmentRuleInputPort,
    DeleteScoringRuleInputPort, GetAssignmentRulesInputPort, GetScoringRulesInputPort,
    UpdateAssignmentRuleInputPort, UpdateScoringRuleInputPort,
)
from application.ports.input.rules.disqualification_rule_use_case_ports import (
    CreateDisqualificationRuleInputPort, DeleteDisqualificationRuleInputPort,
    GetDisqualificationRulesInputPort, UpdateDisqualificationRuleInputPort,
)
from application.ports.input.groups.sales_group_use_case_ports import (
    CreateSalesGroupInputPort, DeleteSalesGroupInputPort, GetSalesGroupsInputPort,
    UpdateSalesGroupInputPort,
)
from application.ports.input.leads.lead_lifecycle_use_case_ports import (
    AssignLeadInputPort, DiscardLeadInputPort, GetLeadInputPort, GetMyLeadsInputPort,
)
from application.use_cases.leads.get_leads_use_case import GetLeadsUseCase
from application.use_cases.leads.get_lead_stats_use_case import GetLeadStatsUseCase
from application.use_cases.rules.assignment_rule_use_cases import CreateAssignmentRuleUseCase, DeleteAssignmentRuleUseCase, GetAssignmentRulesUseCase, UpdateAssignmentRuleUseCase
from application.use_cases.rules.scoring_rule_use_cases import CreateScoringRuleUseCase, DeleteScoringRuleUseCase, GetScoringRulesUseCase, UpdateScoringRuleUseCase
from application.use_cases.rules.disqualification_rule_use_cases import (
    CreateDisqualificationRuleUseCase, DeleteDisqualificationRuleUseCase,
    GetDisqualificationRulesUseCase, UpdateDisqualificationRuleUseCase,
)
from application.use_cases.groups.sales_group_use_cases import (
    CreateSalesGroupUseCase, DeleteSalesGroupUseCase, GetSalesGroupsUseCase, UpdateSalesGroupUseCase,
)
from application.use_cases.leads.lead_lifecycle_use_cases import (
    AssignLeadUseCase, DiscardLeadUseCase, GetLeadUseCase, GetMyLeadsUseCase,
)
from application.ports.input.advisors.advisor_use_case_ports import ListAdvisorsInputPort, SetAdvisorGroupInputPort
from application.use_cases.advisors.advisor_use_cases import ListAdvisorsUseCase, SetAdvisorGroupUseCase
from infrastructure.adapters.input.api.dependencies import get_container, get_uow
from infrastructure.di.container import Container

def get_get_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadsInputPort:
    return GetLeadsUseCase(uow=uow)

def get_get_lead_stats_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadStatsInputPort:
    return GetLeadStatsUseCase(uow=uow)

def get_create_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateScoringRuleInputPort:
    return CreateScoringRuleUseCase(uow=uow)

def get_get_scoring_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetScoringRulesInputPort:
    return GetScoringRulesUseCase(uow=uow)

def get_update_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateScoringRuleInputPort:
    return UpdateScoringRuleUseCase(uow=uow)

def get_delete_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteScoringRuleInputPort:
    return DeleteScoringRuleUseCase(uow=uow)

def get_create_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateAssignmentRuleInputPort:
    return CreateAssignmentRuleUseCase(uow=uow)

def get_get_assignment_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAssignmentRulesInputPort:
    return GetAssignmentRulesUseCase(uow=uow)

def get_update_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateAssignmentRuleInputPort:
    return UpdateAssignmentRuleUseCase(uow=uow)

def get_delete_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteAssignmentRuleInputPort:
    return DeleteAssignmentRuleUseCase(uow=uow)

def get_create_disqualification_rule_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> CreateDisqualificationRuleInputPort:
    return CreateDisqualificationRuleUseCase(uow=uow)

def get_get_disqualification_rules_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> GetDisqualificationRulesInputPort:
    return GetDisqualificationRulesUseCase(uow=uow)

def get_update_disqualification_rule_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> UpdateDisqualificationRuleInputPort:
    return UpdateDisqualificationRuleUseCase(uow=uow)

def get_delete_disqualification_rule_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> DeleteDisqualificationRuleInputPort:
    return DeleteDisqualificationRuleUseCase(uow=uow)

def get_create_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateSalesGroupInputPort:
    return CreateSalesGroupUseCase(uow=uow)

def get_get_sales_groups_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetSalesGroupsInputPort:
    return GetSalesGroupsUseCase(uow=uow)

def get_update_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateSalesGroupInputPort:
    return UpdateSalesGroupUseCase(uow=uow)

def get_delete_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteSalesGroupInputPort:
    return DeleteSalesGroupUseCase(uow=uow)

def get_assign_lead_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), container: Container = Depends(get_container),
) -> AssignLeadInputPort:
    return AssignLeadUseCase(uow=uow, directory=container.advisor_directory)

def get_discard_lead_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DiscardLeadInputPort:
    return DiscardLeadUseCase(uow=uow)

def get_get_my_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetMyLeadsInputPort:
    return GetMyLeadsUseCase(uow=uow)

def get_get_lead_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadInputPort:
    return GetLeadUseCase(uow=uow)

def get_list_advisors_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> ListAdvisorsInputPort:
    return ListAdvisorsUseCase(uow=uow)


def get_set_advisor_group_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), container: Container = Depends(get_container),
) -> SetAdvisorGroupInputPort:
    return SetAdvisorGroupUseCase(uow=uow, directory=container.advisor_directory)
