from typing import Optional
from uuid import UUID

import httpx
from chassis.auth import ServiceTokenClient, ServiceTokenUnavailable

from application.ports.output.advisors.identity_agents_port import IdentityAgentsPort
from domain.advisors.advisor import Advisor
from domain.exceptions import DomainException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId


def _unavailable() -> DomainException:
    return DomainException("identity is unavailable", error_code="SERVICE_UNAVAILABLE")


class HttpIdentityAgents(IdentityAgentsPort):
    """`GET /internal/v1/agents/{agent_id}` (contracts/openapi/identity-internal.v1.yaml)."""

    def __init__(self, identity_url: str, tokens: ServiceTokenClient, client: httpx.Client) -> None:
        self._url = identity_url.rstrip("/") + "/internal/v1/agents/"
        self._tokens = tokens
        self._client = client

    def fetch(self, agent_id: UUID) -> Optional[Advisor]:
        try:
            token = self._tokens.token()
            response = self._client.get(self._url + str(agent_id), headers={"Authorization": f"Bearer {token}"})
        except (ServiceTokenUnavailable, httpx.HTTPError):
            raise _unavailable() from None
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            # A 401 included: a token identity refuses is a misconfiguration
            # here, not an answer about the agent.
            raise _unavailable()
        try:
            body = response.json()
            if body["tenant_id"] is None:
                # The platform administrator: no organization to be an advisor in.
                return None
            return Advisor(
                agent_id=AgentId(body["agent_id"]),
                tenant_id=TenantId(body["tenant_id"]),
                name=body["name"],
                role=AgentRole(body["role"]),
                is_active=bool(body["is_active"]),
                version=int(body["version"]),
            )
        except (ValueError, KeyError, TypeError, DomainException):
            raise _unavailable() from None
