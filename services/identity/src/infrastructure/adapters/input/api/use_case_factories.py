"""Use-case wiring for the routers: one factory per input port, built per request
from the request's unit of work and the container's shared adapters."""
from fastapi import Depends

from application.ports.input.agents import (
    CreateAgentInputPort, DeactivateAgentInputPort, GetAgentInputPort, GetAgentsInputPort,
    GetAgentStateInputPort, IssueIntegrationCredentialInputPort, UpdateAgentInputPort,
)
from application.ports.input.auth import CurrentIdentityInputPort, LoginInputPort, LogoutInputPort
from application.ports.input.mfa import MfaEnrollmentInputPort, MfaLoginInputPort
from application.ports.input.oauth import OAuthChallengeInputPort, SocialLoginInputPort
from application.ports.input.tenants import CreateTenantInputPort, GetTenantsInputPort, UpdateTenantInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.agents.commands import CreateAgentUseCase, DeactivateAgentUseCase, UpdateAgentUseCase
from application.use_cases.agents.integration_credential import IssueIntegrationCredentialUseCase
from application.use_cases.agents.queries import GetAgentStateUseCase, GetAgentsUseCase, GetAgentUseCase
from application.use_cases.auth.login import LoginUseCase
from application.use_cases.auth.session import CurrentIdentityUseCase, LogoutUseCase
from application.use_cases.mfa.enrollment import MfaEnrollmentUseCase
from application.use_cases.mfa.mfa_login import MfaLoginUseCase
from application.use_cases.oauth.oauth_challenge import OAuthChallengeUseCase
from application.use_cases.oauth.social_login import SocialLoginUseCase
from application.use_cases.tenants.create_tenant import CreateTenantUseCase
from application.use_cases.tenants.manage_tenants import GetTenantsUseCase, UpdateTenantUseCase
from infrastructure.adapters.input.api.dependencies import get_container, get_uow
from infrastructure.di.container import Container

_Uow = Depends(get_uow)
_Container = Depends(get_container)


def get_login_use_case(uow: UnitOfWorkPort = _Uow, container: Container = _Container) -> LoginInputPort:
    return LoginUseCase(uow, container.password_hasher, container.settings.session_hours)


def get_logout_use_case(uow: UnitOfWorkPort = _Uow) -> LogoutInputPort:
    return LogoutUseCase(uow)


def get_current_identity_use_case(uow: UnitOfWorkPort = _Uow) -> CurrentIdentityInputPort:
    return CurrentIdentityUseCase(uow)


def get_mfa_enrollment_use_case(
    uow: UnitOfWorkPort = _Uow, container: Container = _Container
) -> MfaEnrollmentInputPort:
    return MfaEnrollmentUseCase(uow, container.password_hasher, container.mfa_crypto)


def get_mfa_login_use_case(uow: UnitOfWorkPort = _Uow, container: Container = _Container) -> MfaLoginInputPort:
    return MfaLoginUseCase(uow, container.mfa_crypto, container.settings.session_hours)


# Each OAuth use case gets a unit of work of its own: the callback consumes the
# challenge and opens the session in two separate transactions.
def get_oauth_challenge_use_case(container: Container = _Container) -> OAuthChallengeInputPort:
    return OAuthChallengeUseCase(container.unit_of_work())


def get_social_login_use_case(container: Container = _Container) -> SocialLoginInputPort:
    return SocialLoginUseCase(container.unit_of_work(), container.settings.session_hours)


def get_get_agents_use_case(uow: UnitOfWorkPort = _Uow) -> GetAgentsInputPort:
    return GetAgentsUseCase(uow)


def get_get_agent_use_case(uow: UnitOfWorkPort = _Uow) -> GetAgentInputPort:
    return GetAgentUseCase(uow)


def get_get_agent_state_use_case(uow: UnitOfWorkPort = _Uow) -> GetAgentStateInputPort:
    return GetAgentStateUseCase(uow)


def get_create_agent_use_case(uow: UnitOfWorkPort = _Uow, container: Container = _Container) -> CreateAgentInputPort:
    return CreateAgentUseCase(uow, container.password_hasher)


def get_update_agent_use_case(uow: UnitOfWorkPort = _Uow) -> UpdateAgentInputPort:
    return UpdateAgentUseCase(uow)


def get_deactivate_agent_use_case(
    uow: UnitOfWorkPort = _Uow, container: Container = _Container
) -> DeactivateAgentInputPort:
    return DeactivateAgentUseCase(uow, container.messaging_provisioner)


def get_issue_integration_credential_use_case(
    uow: UnitOfWorkPort = _Uow, container: Container = _Container
) -> IssueIntegrationCredentialInputPort:
    return IssueIntegrationCredentialUseCase(uow, container.password_hasher, container.messaging_provisioner)


def get_create_tenant_use_case(uow: UnitOfWorkPort = _Uow, container: Container = _Container) -> CreateTenantInputPort:
    return CreateTenantUseCase(uow, container.password_hasher)


def get_get_tenants_use_case(uow: UnitOfWorkPort = _Uow) -> GetTenantsInputPort:
    return GetTenantsUseCase(uow)


def get_update_tenant_use_case(uow: UnitOfWorkPort = _Uow) -> UpdateTenantInputPort:
    return UpdateTenantUseCase(uow)
