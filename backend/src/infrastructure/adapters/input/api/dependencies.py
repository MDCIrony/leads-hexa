from typing import Optional
from uuid import UUID
from fastapi import Request, Depends
from chassis.auth import KeysUnavailable, TokenError
from application.dtos.context import Principal, RequestContext
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
from domain.exceptions import DomainException, UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from infrastructure.di.container import Container

def get_container(request: Request) -> Container:
    return request.app.state.container

def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()

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


def build_request_context(principal: Principal) -> RequestContext:
    """The organization always comes from the verified identity, never from the
    request path or body."""
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        raise UnauthorizedException("Authentication required")
    return token.strip() or None


def _principal_from_token(token: str, container: Container) -> Principal:
    try:
        claims = container.token_verifier.verify(token)
        return Principal(
            id=UUID(claims.sub),
            tenant_id=UUID(claims.tid) if claims.tid else None,
            role=AgentRole(claims.role),
            principal_type=claims.ptype,
        )
    except KeysUnavailable as error:  # before TokenError, its parent: an outage is not the caller's fault
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise UnauthorizedException("Authentication required") from error


def get_principal(request: Request, container: Container = Depends(get_container)) -> Principal:
    """The bearer is the gateway's, never the client's: nginx overwrites it."""
    token = bearer_token(request)
    if token is None:
        raise UnauthorizedException("Authentication required")
    return _principal_from_token(token, container)


def get_request_context(principal: Principal = Depends(get_principal)) -> RequestContext:
    """Rejects ptype=integration: a machine credential reaches only the route
    that composes require_manager_or_integration."""
    if principal.principal_type == "integration":
        raise UnauthorizedException("Authentication required")
    return build_request_context(principal)


def require_organization_manager(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.principal)
    return context


def require_organization_member(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Any member of an organization: manager or sales agent.

    The platform admin has no tenant, so it is excluded by construction —
    which is the point: it must not reach operational data."""
    AuthorizationPolicy.ensure_can_access_tenant(context.principal, context.tenant_id)
    return context


def require_manager_or_integration(principal: Principal = Depends(get_principal)) -> RequestContext:
    """Composes the two authentication paths at exactly one route (GET
    /leads) instead of branching inside a shared handler — authorization by
    routing, the same shape require_organization_member vs.
    require_organization_manager already use."""
    if principal.principal_type != "integration":
        AuthorizationPolicy.ensure_can_manage_organization(principal)
    return build_request_context(principal)
