"""Rows written straight through the persistence adapters, for states the API
cannot reach on its own (an expired session, an integration agent without Kafka)."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from domain.agents.agent import Agent
from domain.sessions.auth_session import AuthSession
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher

PASSWORD = "Secret123"
# Default for seed_agent: an organization of its own, so None can still mean "no organization".
_OWN_TENANT = object()
HASHED = BcryptPasswordHasher().hash(PASSWORD)


def unit_of_work(client) -> PostgresUnitOfWork:
    # The container only exists for the lifespan of the app, so seeding runs inside the client block.
    return PostgresUnitOfWork(client.app.state.container.database)


def seed_agent(client, role=AgentRole.MANAGER, tenant_id=_OWN_TENANT, is_active=True, hashed_password=HASHED) -> Agent:
    agent = Agent.create(
        name="Seeded", email=f"seed_{uuid.uuid4().hex[:8]}@test.com", role=role,
        hashed_password=hashed_password, tenant_id=uuid.uuid4() if tenant_id is _OWN_TENANT else tenant_id, is_active=is_active,
    )
    with unit_of_work(client) as uow:
        return uow.agents.save(agent)


def seed_tenant(client, is_active=True) -> Tenant:
    with unit_of_work(client) as uow:
        return uow.tenants.save(Tenant.create(name=f"Org {uuid.uuid4().hex[:8]}", is_active=is_active))


def save_session(client, agent: Agent, token: str | None = None, expires_in=timedelta(hours=8)) -> str:
    token = token or secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + expires_in
    with unit_of_work(client) as uow:
        uow.sessions.save(AuthSession(
            token_hash=sha256(token.encode()).hexdigest(), agent_id=agent.id.value,
            created_at=expires_at - timedelta(hours=8), expires_at=expires_at,
        ))
    return token


def cookie(token: str) -> dict:
    return {"Cookie": f"leads_session={token}"}


def session_headers(client, agent: Agent) -> dict:
    return cookie(save_session(client, agent))


def login(client, email: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def bootstrap_admin(client) -> dict:
    """The platform admin through the anonymous bootstrap, then its session cookie.
    Only works on an empty agents table, which every e2e test starts from."""
    email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
    created = client.post("/api/v1/agents", json={"name": "Platform Admin", "email": email, "password": PASSWORD})
    assert created.status_code == 201, created.text
    token = login(client, email).cookies["leads_session"]
    # The jar would otherwise carry the admin session into every later "anonymous" call.
    client.cookies.clear()
    return cookie(token)


def create_organization(client, admin_headers: dict) -> tuple[dict, dict]:
    """A tenant with its manager, created on the platform plane; returns the body and the manager's cookie."""
    email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    created = client.post(
        "/api/v1/tenants",
        json={"name": f"Org {uuid.uuid4().hex[:6]}", "manager": {"name": "Manager", "email": email, "password": PASSWORD}},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    manager_login = login(client, email)
    assert manager_login.status_code == 200
    client.cookies.clear()
    return created.json(), cookie(manager_login.cookies["leads_session"])


def create_agent(client, headers: dict, **fields):
    body = {"name": "Agent", "email": f"agent_{uuid.uuid4().hex[:6]}@example.com", "password": PASSWORD, **fields}
    return client.post("/api/v1/agents", json=body, headers=headers)
