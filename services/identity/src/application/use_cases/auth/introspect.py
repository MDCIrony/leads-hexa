from datetime import datetime, timezone
from uuid import UUID

from application.dtos.auth import IntrospectionResult
from application.ports.input.auth import IntrospectInputPort
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import token_hash
from domain.agents.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.value_objects.agent_role import AgentRole


class IntrospectUseCase(IntrospectInputPort):
    """Says who the caller is, never whether they may do something: that stays in
    each service, on the Principal."""

    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(
        self, api_key: str | None, session_token: str | None, optional: bool = False
    ) -> IntrospectionResult | None:
        # A present but invalid credential never degrades to anonymous.
        if api_key:
            return IntrospectionResult(self._integration_agent(api_key), "integration")
        if session_token:
            return IntrospectionResult(self._session_agent(session_token), "human")
        if optional:
            return None
        raise UnauthorizedException("Authentication required")

    def _session_agent(self, token: str) -> Agent:
        with self.uow:
            session = self.uow.sessions.get_active(token_hash(token), datetime.now(timezone.utc))
            agent = self.uow.agents.get_by_id(session.agent_id) if session else None
            usable = self._usable(agent)
        if not usable:
            raise UnauthorizedException("Agent no longer exists or is inactive")
        return agent

    def _integration_agent(self, api_key: str) -> Agent:
        try:
            agent_id, secret = api_key.split(".", 1)
            parsed_id = UUID(agent_id)
        except ValueError as error:
            raise UnauthorizedException("Malformed API key") from error
        with self.uow:
            agent = self.uow.agents.get_by_id(parsed_id)
            usable = self._usable(agent)
        if (
            not usable
            or agent.role != AgentRole.INTEGRATION
            or not agent.hashed_password
            or not self.password_hasher.verify(secret, agent.hashed_password)
        ):
            raise UnauthorizedException("Invalid API key")
        return agent

    def _usable(self, agent: Agent | None) -> bool:
        if not agent or not agent.is_active:
            return False
        if agent.tenant_id is None:
            return True
        # Suspending a tenant deactivates its agents, but an agent reactivated on its
        # own afterwards must still not get in while the organization stays suspended.
        # A missing tenant row is not treated as suspended: backfilling it is sync_tenants' job.
        tenant = self.uow.tenants.get_by_id(agent.tenant_id.value)
        return tenant is None or tenant.is_active
