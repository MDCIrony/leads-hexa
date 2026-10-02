from datetime import datetime, timezone

from application.dtos.auth import CurrentIdentityResult
from application.ports.input.auth import CurrentIdentityInputPort, LogoutInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import token_hash
from domain.agents.agent import Agent


class LogoutUseCase(LogoutInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, session_token: str | None) -> None:
        if not session_token:
            return
        with self.uow:
            self.uow.sessions.revoke(token_hash(session_token), datetime.now(timezone.utc))


class CurrentIdentityUseCase(CurrentIdentityInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, agent: Agent) -> CurrentIdentityResult:
        with self.uow:
            tenant = self.uow.tenants.get_by_id(agent.tenant_id.value) if agent.tenant_id else None
            enrollment = self.uow.mfa.get(agent.id.value)
            providers = [identity.provider for identity in self.uow.social_identities.list_by_agent(agent.id.value)]
        return CurrentIdentityResult(
            agent=agent,
            tenant_name=tenant.name if tenant else None,
            mfa_enabled=bool(enrollment and enrollment.enabled_at),
            linked_oauth_providers=providers,
        )
