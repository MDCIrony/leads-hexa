from typing import Optional
from uuid import UUID
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer
from application.dtos.context import RequestContext
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.ports.output.token_service_port import TokenServicePort
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, DeactivateAgentInputPort, GetAgentsInputPort, GetAgentInputPort,
    UpdateAgentInputPort,
)
from application.ports.input.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, CreateScoringRuleInputPort, DeleteAssignmentRuleInputPort,
    GetAssignmentRulesInputPort, GetScoringRulesInputPort, UpdateAssignmentRuleInputPort,
)
from application.ports.input.sales_group_use_case_ports import (
    CreateSalesGroupInputPort, DeleteSalesGroupInputPort, GetSalesGroupsInputPort,
    UpdateSalesGroupInputPort,
)
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.get_leads_use_case import GetLeadsUseCase
from application.use_cases.agent_use_cases import (
    CreateAgentUseCase, DeactivateAgentUseCase, GetAgentsUseCase, GetAgentUseCase, UpdateAgentUseCase,
)
from application.use_cases.rule_use_cases import (
    CreateAssignmentRuleUseCase, CreateScoringRuleUseCase, DeleteAssignmentRuleUseCase,
    GetAssignmentRulesUseCase, GetScoringRulesUseCase, UpdateAssignmentRuleUseCase,
)
from application.use_cases.sales_group_use_cases import (
    CreateSalesGroupUseCase, DeleteSalesGroupUseCase, GetSalesGroupsUseCase, UpdateSalesGroupUseCase,
)
from application.ports.input.auth_use_case_port import LoginInputPort
from application.use_cases.auth_use_cases import LoginUseCase
from application.ports.input.tenant_use_case_ports import (
    CreateTenantInputPort, GetTenantsInputPort, UpdateTenantInputPort
)
from application.use_cases.tenant_use_cases import CreateTenantUseCase, GetTenantsUseCase, UpdateTenantUseCase
from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from infrastructure.di.container import Container

def get_container(request: Request) -> Container:
    return request.app.state.container

def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()

def get_token_service(container: Container = Depends(get_container)) -> TokenServicePort:
    return container.token_service

def get_ingest_lead_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> IngestLeadInputPort:
    return IngestLeadUseCase(
        uow=uow,
        event_publisher=container.event_publisher,
        engine=container.assignment_engine,
    )

def get_process_batch_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> ProcessBatchInputPort:
    ingest_lead_use_case = IngestLeadUseCase(
        uow=uow,
        event_publisher=container.event_publisher,
        engine=container.assignment_engine,
    )
    return ProcessBatchUseCase(file_parser=container.file_parser, ingest_lead_use_case=ingest_lead_use_case)

def get_get_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadsInputPort:
    return GetLeadsUseCase(uow=uow)

def get_create_agent_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> CreateAgentInputPort:
    return CreateAgentUseCase(uow=uow, password_hasher=container.password_hasher)

def get_get_agents_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentsInputPort:
    return GetAgentsUseCase(uow=uow)

def get_get_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentInputPort:
    return GetAgentUseCase(uow=uow)

def get_update_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateAgentInputPort:
    return UpdateAgentUseCase(uow=uow)

def get_deactivate_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeactivateAgentInputPort:
    return DeactivateAgentUseCase(uow=uow)

def get_create_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateScoringRuleInputPort:
    return CreateScoringRuleUseCase(uow=uow)

def get_get_scoring_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetScoringRulesInputPort:
    return GetScoringRulesUseCase(uow=uow)

def get_create_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateAssignmentRuleInputPort:
    return CreateAssignmentRuleUseCase(uow=uow)

def get_get_assignment_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAssignmentRulesInputPort:
    return GetAssignmentRulesUseCase(uow=uow)

def get_update_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateAssignmentRuleInputPort:
    return UpdateAssignmentRuleUseCase(uow=uow)

def get_delete_assignment_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteAssignmentRuleInputPort:
    return DeleteAssignmentRuleUseCase(uow=uow)

def get_create_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateSalesGroupInputPort:
    return CreateSalesGroupUseCase(uow=uow)

def get_get_sales_groups_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetSalesGroupsInputPort:
    return GetSalesGroupsUseCase(uow=uow)

def get_update_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateSalesGroupInputPort:
    return UpdateSalesGroupUseCase(uow=uow)

def get_delete_sales_group_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteSalesGroupInputPort:
    return DeleteSalesGroupUseCase(uow=uow)

def get_login_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> LoginInputPort:
    return LoginUseCase(
        uow=uow,
        password_hasher=container.password_hasher,
        token_service=container.token_service,
    )

def get_create_tenant_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> CreateTenantInputPort:
    return CreateTenantUseCase(uow=uow, password_hasher=container.password_hasher)

def get_get_tenants_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetTenantsInputPort:
    return GetTenantsUseCase(uow=uow)

def get_update_tenant_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateTenantInputPort:
    return UpdateTenantUseCase(uow=uow)


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def resolve_current_agent(token: str, uow: UnitOfWorkPort, token_service: TokenServicePort) -> Agent:
    """Pure function so it can be tested without FastAPI's dependency machinery."""
    claims = token_service.verify(token)

    with uow:
        agent = uow.agents.get_by_id(UUID(claims.agent_id))

    if not agent or not agent.is_active:
        raise UnauthorizedException("Agent no longer exists or is inactive")
    return agent


def get_current_agent(
    token: str = Depends(_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
    token_service: TokenServicePort = Depends(get_token_service),
) -> Agent:
    return resolve_current_agent(token=token, uow=uow, token_service=token_service)


def get_optional_current_agent(
    token: Optional[str] = Depends(_optional_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
    token_service: TokenServicePort = Depends(get_token_service),
) -> Optional[Agent]:
    if not token:
        return None
    try:
        return resolve_current_agent(token=token, uow=uow, token_service=token_service)
    except UnauthorizedException:
        return None


def build_request_context(current_agent: Agent) -> RequestContext:
    """The organization always comes from the verified identity, never from the
    request path or body."""
    tenant_id = UUID(str(current_agent.tenant_id)) if current_agent.tenant_id else None
    return RequestContext(actor=current_agent, tenant_id=tenant_id)


def get_request_context(current_agent: Agent = Depends(get_current_agent)) -> RequestContext:
    return build_request_context(current_agent=current_agent)


def require_organization_manager(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.actor)
    return context


def require_platform_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_platform(context.actor)
    return context
