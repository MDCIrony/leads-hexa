from typing import Optional
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID
from fastapi import Request, Depends
from fastapi.security import APIKeyHeader
from application.dtos.context import Principal, RequestContext
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.ports.output.job_queue_port import JobQueuePort
from application.ports.output.messaging_credential_provisioner_port import MessagingCredentialProvisionerPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.intake_phase_use_case_ports import (
    ProcessIntakeJobInputPort, ReceiveIntakeInputPort,
)
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.get_lead_stats_use_case_port import GetLeadStatsInputPort
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, DeactivateAgentInputPort, GetAgentsInputPort, GetAgentInputPort,
    IssueIntegrationCredentialInputPort, UpdateAgentInputPort,
)
from application.ports.input.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, CreateScoringRuleInputPort, DeleteAssignmentRuleInputPort,
    DeleteScoringRuleInputPort, GetAssignmentRulesInputPort, GetScoringRulesInputPort,
    UpdateAssignmentRuleInputPort, UpdateScoringRuleInputPort,
)
from application.ports.input.disqualification_rule_use_case_ports import (
    CreateDisqualificationRuleInputPort, DeleteDisqualificationRuleInputPort,
    GetDisqualificationRulesInputPort, UpdateDisqualificationRuleInputPort,
)
from application.ports.input.sales_group_use_case_ports import (
    CreateSalesGroupInputPort, DeleteSalesGroupInputPort, GetSalesGroupsInputPort,
    UpdateSalesGroupInputPort,
)
from application.ports.input.lead_source_use_case_ports import (
    CreateLeadSourceInputPort, DeleteLeadSourceInputPort, GetLeadSourcesInputPort,
    UpdateLeadSourceInputPort,
)
from application.ports.input.lead_lifecycle_use_case_ports import (
    AssignLeadInputPort, DiscardLeadInputPort, GetLeadInputPort, GetMyLeadsInputPort,
)
from application.ports.input.intake_record_use_case_ports import (
    DiscardIntakeRecordInputPort, GetIntakeRecordsInputPort, PromoteIntakeRecordInputPort,
)
from application.ports.input.intake_job_use_case_ports import (
    GetIntakeJobInputPort, GetIntakeJobsInputPort, ReprocessIntakeJobInputPort,
)
from application.ports.input.notification_use_case_ports import (
    GetNotificationsInputPort, MarkAllNotificationsReadInputPort, MarkNotificationReadInputPort,
)
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.process_intake_job_use_case import ProcessIntakeJobUseCase
from application.use_cases.receive_intake_use_case import ReceiveIntakeUseCase
from application.use_cases.get_leads_use_case import GetLeadsUseCase
from application.use_cases.get_lead_stats_use_case import GetLeadStatsUseCase
from application.use_cases.agent_use_cases import (
    CreateAgentUseCase, DeactivateAgentUseCase, GetAgentsUseCase, GetAgentUseCase,
    IssueIntegrationCredentialUseCase, UpdateAgentUseCase,
)
from application.use_cases.rule_use_cases import (
    CreateAssignmentRuleUseCase, CreateScoringRuleUseCase, DeleteAssignmentRuleUseCase,
    DeleteScoringRuleUseCase, GetAssignmentRulesUseCase, GetScoringRulesUseCase,
    UpdateAssignmentRuleUseCase, UpdateScoringRuleUseCase,
)
from application.use_cases.disqualification_rule_use_cases import (
    CreateDisqualificationRuleUseCase, DeleteDisqualificationRuleUseCase,
    GetDisqualificationRulesUseCase, UpdateDisqualificationRuleUseCase,
)
from application.use_cases.sales_group_use_cases import (
    CreateSalesGroupUseCase, DeleteSalesGroupUseCase, GetSalesGroupsUseCase, UpdateSalesGroupUseCase,
)
from application.use_cases.lead_source_use_cases import (
    CreateLeadSourceUseCase, DeleteLeadSourceUseCase, GetLeadSourcesUseCase, UpdateLeadSourceUseCase,
)
from application.use_cases.lead_lifecycle_use_cases import (
    AssignLeadUseCase, DiscardLeadUseCase, GetLeadUseCase, GetMyLeadsUseCase,
)
from application.use_cases.intake_record_use_cases import (
    DiscardIntakeRecordUseCase, GetIntakeRecordsUseCase, PromoteIntakeRecordUseCase,
)
from application.use_cases.intake_job_use_cases import (
    GetIntakeJobUseCase, GetIntakeJobsUseCase, ReprocessIntakeJobUseCase,
)
from application.use_cases.notification_use_cases import (
    GetNotificationsUseCase, MarkAllNotificationsReadUseCase, MarkNotificationReadUseCase,
)
from application.ports.input.auth_use_case_port import LoginInputPort
from application.use_cases.auth_use_cases import (
    LoginUseCase, MfaUseCase, OAuthChallengeUseCase, SocialLoginUseCase,
)
from application.ports.input.tenant_use_case_ports import (
    CreateTenantInputPort, GetTenantsInputPort, UpdateTenantInputPort
)
from application.use_cases.tenant_use_cases import CreateTenantUseCase, GetTenantsUseCase, UpdateTenantUseCase
from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from infrastructure.di.container import Container

def get_container(request: Request) -> Container:
    return request.app.state.container

def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()

def get_job_queue(container: Container = Depends(get_container)) -> JobQueuePort:
    return container.job_queue

def get_ingest_lead_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> IngestLeadInputPort:
    return IngestLeadUseCase(
        uow=uow,
        event_publisher=container.event_publisher,
        engine=container.assignment_engine,
    )

def get_get_intake_records_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeRecordsInputPort:
    return GetIntakeRecordsUseCase(uow=uow)

def get_receive_intake_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> ReceiveIntakeInputPort:
    return ReceiveIntakeUseCase(uow=uow)

def get_process_intake_job_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    ingest: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
) -> ProcessIntakeJobInputPort:
    return ProcessIntakeJobUseCase(uow=uow, ingest=ingest)

# Defined after get_process_intake_job_use_case, not before: its own default
# argument references that name, and Python resolves defaults at def-time.
def get_process_batch_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
    process_job: ProcessIntakeJobInputPort = Depends(get_process_intake_job_use_case),
) -> ProcessBatchInputPort:
    return ProcessBatchUseCase(
        uow=uow,
        file_parser=container.file_parser,
        process_job=process_job,
        job_queue=container.job_queue,
    )

def get_promote_intake_record_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    ingest: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
) -> PromoteIntakeRecordInputPort:
    return PromoteIntakeRecordUseCase(uow=uow, ingest=ingest)

def get_discard_intake_record_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DiscardIntakeRecordInputPort:
    return DiscardIntakeRecordUseCase(uow=uow)

def get_get_intake_jobs_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeJobsInputPort:
    return GetIntakeJobsUseCase(uow=uow)

def get_get_intake_job_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetIntakeJobInputPort:
    return GetIntakeJobUseCase(uow=uow)

# Depends on get_process_intake_job_use_case, defined above: same def-time
# default-argument resolution as get_process_batch_use_case below.
def get_reprocess_intake_job_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    process: ProcessIntakeJobInputPort = Depends(get_process_intake_job_use_case),
) -> ReprocessIntakeJobInputPort:
    return ReprocessIntakeJobUseCase(uow=uow, process=process)

def get_get_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadsInputPort:
    return GetLeadsUseCase(uow=uow)

def get_get_lead_stats_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadStatsInputPort:
    return GetLeadStatsUseCase(uow=uow)

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

def get_deactivate_agent_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> DeactivateAgentInputPort:
    return DeactivateAgentUseCase(uow=uow, messaging_provisioner=container.messaging_credential_provisioner)

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

def get_create_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateLeadSourceInputPort:
    return CreateLeadSourceUseCase(uow=uow)

def get_get_lead_sources_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadSourcesInputPort:
    return GetLeadSourcesUseCase(uow=uow)

def get_update_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> UpdateLeadSourceInputPort:
    return UpdateLeadSourceUseCase(uow=uow)

def get_delete_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DeleteLeadSourceInputPort:
    return DeleteLeadSourceUseCase(uow=uow)

def get_assign_lead_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> AssignLeadInputPort:
    return AssignLeadUseCase(uow=uow, event_publisher=container.event_publisher)

def get_discard_lead_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> DiscardLeadInputPort:
    return DiscardLeadUseCase(uow=uow)

def get_get_my_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetMyLeadsInputPort:
    return GetMyLeadsUseCase(uow=uow)

def get_get_lead_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadInputPort:
    return GetLeadUseCase(uow=uow)

def get_login_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> LoginInputPort:
    return LoginUseCase(
        uow=uow,
        password_hasher=container.password_hasher,
        session_hours=container.settings.session_hours,
    )

def get_mfa_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> MfaUseCase:
    return MfaUseCase(
        uow=uow,
        password_hasher=container.password_hasher,
        crypto=container.mfa_crypto,
        session_hours=container.settings.session_hours,
    )

def get_oauth_challenge_use_case(
    container: Container = Depends(get_container),
) -> OAuthChallengeUseCase:
    return OAuthChallengeUseCase(uow=container.unit_of_work())

def get_social_login_use_case(
    container: Container = Depends(get_container),
) -> SocialLoginUseCase:
    return SocialLoginUseCase(
        uow=container.unit_of_work(), session_hours=container.settings.session_hours,
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

def get_get_notifications_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetNotificationsInputPort:
    return GetNotificationsUseCase(uow=uow)

def get_mark_notification_read_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> MarkNotificationReadInputPort:
    return MarkNotificationReadUseCase(uow=uow)

def get_mark_all_notifications_read_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
) -> MarkAllNotificationsReadInputPort:
    return MarkAllNotificationsReadUseCase(uow=uow)


# Its own header, deliberately not a second scheme sniffed out of
# Authorization: Bearer — that would make the two authentication paths
# depend on parsing one shared header instead of staying visibly separate.
_api_key_scheme = APIKeyHeader(name="X-Api-Key", auto_error=False)


def resolve_current_agent(token: str, uow: UnitOfWorkPort) -> Agent:
    """Pure function so it can be tested without FastAPI's dependency machinery."""
    with uow:
        session = uow.sessions.get_active(sha256(token.encode()).hexdigest(), datetime.now(timezone.utc))
        agent = uow.agents.get_by_id(session.agent_id) if session else None

    if not agent or not agent.is_active:
        raise UnauthorizedException("Agent no longer exists or is inactive")
    return agent


def get_current_agent(
    request: Request,
    uow: UnitOfWorkPort = Depends(get_uow),
) -> Agent:
    token = request.cookies.get("leads_session")
    if not token:
        raise UnauthorizedException("Authentication required")
    return resolve_current_agent(token=token, uow=uow)


def get_optional_current_agent(
    request: Request,
    uow: UnitOfWorkPort = Depends(get_uow),
) -> Optional[Agent]:
    token = request.cookies.get("leads_session")
    if not token:
        return None
    try:
        return resolve_current_agent(token=token, uow=uow)
    except UnauthorizedException:
        return None


def principal_from_agent(agent: Agent) -> Principal:
    return Principal(
        id=agent.id.value,
        tenant_id=agent.tenant_id.value if agent.tenant_id else None,
        role=agent.role,
        principal_type="integration" if agent.role == AgentRole.INTEGRATION else "human",
    )


def build_request_context(principal: Principal) -> RequestContext:
    """The organization always comes from the verified identity, never from the
    request path or body."""
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def get_request_context(current_agent: Agent = Depends(get_current_agent)) -> RequestContext:
    return build_request_context(principal_from_agent(current_agent))


def require_organization_manager(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.principal)
    return context


def require_platform_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_platform(context.principal)
    return context


def require_organization_member(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Any member of an organization: manager or sales agent.

    The platform admin has no tenant, so it is excluded by construction —
    which is the point: it must not reach operational data."""
    AuthorizationPolicy.ensure_can_access_tenant(context.principal, context.tenant_id)
    return context


def resolve_integration_agent(
    api_key: str, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort
) -> Agent:
    """Pure function, same shape as resolve_current_agent: testable without
    FastAPI's dependency machinery."""
    try:
        agent_id_str, secret = api_key.split(".", 1)
        agent_id = UUID(agent_id_str)
    except ValueError as error:
        raise UnauthorizedException("Malformed API key") from error

    with uow:
        agent = uow.agents.get_by_id(agent_id)

    if (
        not agent
        or not agent.is_active
        or agent.role != AgentRole.INTEGRATION
        or not agent.hashed_password
        or not password_hasher.verify(secret, agent.hashed_password)
    ):
        raise UnauthorizedException("Invalid API key")
    return agent


def resolve_integration_context(
    api_key: str, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort
) -> RequestContext:
    return build_request_context(principal_from_agent(resolve_integration_agent(api_key, uow, password_hasher)))


def require_manager_or_integration(
    api_key: Optional[str] = Depends(_api_key_scheme),
    current_agent: Optional[Agent] = Depends(get_optional_current_agent),
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> RequestContext:
    """Composes the two authentication paths at exactly one route (GET
    /leads) instead of branching inside a shared handler — authorization by
    routing, the same shape require_organization_member vs.
    require_organization_manager already use."""
    if api_key:
        return resolve_integration_context(api_key, uow, container.password_hasher)
    if current_agent is not None:
        context = build_request_context(principal_from_agent(current_agent))
        AuthorizationPolicy.ensure_can_manage_organization(context.principal)
        return context
    raise UnauthorizedException("Authentication required")


def get_messaging_credential_provisioner(
    container: Container = Depends(get_container),
) -> MessagingCredentialProvisionerPort:
    return container.messaging_credential_provisioner


def get_issue_integration_credential_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> IssueIntegrationCredentialInputPort:
    return IssueIntegrationCredentialUseCase(
        uow=uow,
        password_hasher=container.password_hasher,
        messaging_provisioner=container.messaging_credential_provisioner,
    )
