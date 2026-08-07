import os
from typing import Generator, Callable, Optional
from uuid import UUID
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, GetAgentsInputPort, GetAgentInputPort
)
from application.ports.input.rule_use_case_ports import (
    CreateScoringRuleInputPort, GetScoringRulesInputPort,
    CreateRoutingRuleInputPort, GetRoutingRulesInputPort
)
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.get_leads_use_case import GetLeadsUseCase
from application.use_cases.agent_use_cases import CreateAgentUseCase, GetAgentsUseCase, GetAgentUseCase
from application.use_cases.rule_use_cases import CreateScoringRuleUseCase, GetScoringRulesUseCase, CreateRoutingRuleUseCase, GetRoutingRulesUseCase
from application.ports.input.auth_use_case_port import LoginInputPort
from application.use_cases.auth_use_cases import LoginUseCase
from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException, ForbiddenException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService

def get_db(request: Request) -> RawSqlDatabase:
    return request.app.state.db

def get_uow(db: RawSqlDatabase = Depends(get_db)) -> Generator[UnitOfWorkPort, None, None]:
    uow = PostgresUnitOfWork(db)
    yield uow

def get_ingest_lead_use_case(request: Request, uow: UnitOfWorkPort = Depends(get_uow)) -> IngestLeadInputPort:
    return IngestLeadUseCase(uow=uow, event_publisher=getattr(request.app.state, "event_publisher", None))

def get_process_batch_use_case(request: Request, uow: UnitOfWorkPort = Depends(get_uow)) -> ProcessBatchInputPort:
    ingest_lead_use_case = IngestLeadUseCase(uow=uow, event_publisher=getattr(request.app.state, "event_publisher", None))
    return ProcessBatchUseCase(file_parser=request.app.state.file_parser, ingest_lead_use_case=ingest_lead_use_case)

def get_get_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadsInputPort:
    return GetLeadsUseCase(uow=uow)

def get_create_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateAgentInputPort:
    return CreateAgentUseCase(uow=uow, password_hasher=BcryptPasswordHasher())

def get_get_agents_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentsInputPort:
    return GetAgentsUseCase(uow=uow)

def get_get_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentInputPort:
    return GetAgentUseCase(uow=uow)

def get_create_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateScoringRuleInputPort:
    return CreateScoringRuleUseCase(uow=uow)

def get_get_scoring_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetScoringRulesInputPort:
    return GetScoringRulesUseCase(uow=uow)

def get_create_routing_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateRoutingRuleInputPort:
    return CreateRoutingRuleUseCase(uow=uow)

def get_get_routing_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetRoutingRulesInputPort:
    return GetRoutingRulesUseCase(uow=uow)

def get_login_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> LoginInputPort:
    return LoginUseCase(
        uow=uow,
        password_hasher=BcryptPasswordHasher(),
        token_service=JwtTokenService(secret=os.environ["JWT_SECRET"]),
    )


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_agent(
    token: str = Depends(_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
) -> Agent:
    claims = JwtTokenService(secret=os.environ["JWT_SECRET"]).verify(token)

    with uow:
        agent = uow.agents.get_by_id(UUID(claims.agent_id))

    if not agent or not agent.is_active:
        raise UnauthorizedException("Agent no longer exists or is inactive")
    return agent


def get_optional_current_agent(
    token: Optional[str] = Depends(_optional_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
) -> Optional[Agent]:
    if not token:
        return None
    try:
        return get_current_agent(token=token, uow=uow)
    except UnauthorizedException:
        return None


def require_role(*allowed_roles: AgentRole) -> Callable[..., Agent]:
    def dependency(current_agent: Agent = Depends(get_current_agent)) -> Agent:
        if current_agent.role not in allowed_roles:
            raise ForbiddenException(f"Role {current_agent.role.value} is not permitted to perform this action")
        return current_agent
    return dependency


def verify_tenant_access(
    tenant_id: UUID,
    current_agent: Agent = Depends(get_current_agent),
) -> Agent:
    if current_agent.role != AgentRole.ADMIN:
        if current_agent.tenant_id is None or str(current_agent.tenant_id) != str(tenant_id):
            raise ForbiddenException("You do not have access to this tenant's data")
    return current_agent


def require_role_and_tenant(*allowed_roles: AgentRole) -> Callable[..., Agent]:
    role_checker = require_role(*allowed_roles)

    def dependency(
        tenant_id: UUID,
        current_agent: Agent = Depends(role_checker),
    ) -> Agent:
        if current_agent.role != AgentRole.ADMIN:
            if current_agent.tenant_id is None or str(current_agent.tenant_id) != str(tenant_id):
                raise ForbiddenException("You do not have access to this tenant's data")
        return current_agent

    return dependency

