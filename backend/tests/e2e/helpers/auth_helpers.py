"""Organizations and principals as identity would hand them to lead-core.

The token alone authenticates a caller here, so a manager or an integration
needs no row. A person work can be given to is also seeded as an advisor,
the projection lead-core routes over."""
from uuid import uuid4

from domain.value_objects.enums import AgentRole
from infrastructure.main import app
from tests.advisors_sync import seed_advisor
from tests.e2e.helpers.gateway_client import as_principal, tenant_of


def _database():
    return app.state.container.database


def principal_of(advisor) -> dict:
    return as_principal(advisor.agent_id, advisor.tenant_id, advisor.role.value)


def manager_headers(tenant_id) -> dict:
    return as_principal(uuid4(), tenant_id, "MANAGER")


def seed_manager(tenant_id, name: str = "Manager") -> dict:
    """A manager that is also in the projection: identity publishes managers too."""
    return principal_of(seed_advisor(_database(), tenant_id, AgentRole.MANAGER, name))


def seed_agent(tenant_id, name: str = "Agent", group_id=None, is_active: bool = True) -> tuple[dict, str]:
    advisor = seed_advisor(_database(), tenant_id, AgentRole.AGENT, name, group_id, is_active)
    return principal_of(advisor), str(advisor.agent_id)


def seed_org_manager(name: str = "Manager") -> dict:
    """The manager of a fresh organization (an id is all one takes)."""
    return seed_manager(uuid4(), name)


def agent_of(manager: dict, name: str = "Agent", group_id=None) -> tuple[dict, str]:
    """An agent of the same organization as `manager`."""
    return seed_agent(tenant_of(manager), name, group_id)


def admin_headers() -> dict:
    return as_principal(uuid4(), None, "ADMIN")


def integration_headers(tenant_id) -> dict:
    return as_principal(uuid4(), tenant_id, "INTEGRATION", "integration")
