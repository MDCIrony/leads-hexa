from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from application.use_cases.auth.session import CurrentIdentityUseCase, LogoutUseCase
from domain.agents.agent import Agent
from domain.mfa.agent_mfa import AgentMfa
from domain.sessions.auth_session import AuthSession
from domain.social.social_identity import SocialIdentity
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def test_logout_revokes_the_session():
    uow = InMemoryUnitOfWork()
    now = datetime.now(timezone.utc)
    key = sha256(b"session").hexdigest()
    uow.sessions.save(AuthSession(key, uuid4(), now, now + timedelta(hours=1)))

    LogoutUseCase(uow).execute("session")

    assert uow.sessions.items[key].revoked_at is not None


def test_logout_without_a_session_is_not_an_error():
    LogoutUseCase(InMemoryUnitOfWork()).execute(None)


def test_current_identity_composes_tenant_mfa_and_linked_providers():
    uow = InMemoryUnitOfWork()
    tenant = uow.tenants.save(Tenant.create(name="Acme"))
    agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", role=AgentRole.MANAGER, tenant_id=tenant.id))
    now = datetime.now(timezone.utc)
    uow.mfa.items[agent.id.value] = AgentMfa(agent.id.value, "ciphertext", enabled_at=now)
    for provider in ("GITHUB", "GOOGLE"):
        uow.social_identities.save(SocialIdentity(uuid4(), agent.id.value, provider, f"sub-{provider}", agent.email, now, now))

    result = CurrentIdentityUseCase(uow).execute(agent)

    assert result.agent is agent
    assert result.tenant_name == "Acme"
    assert result.mfa_enabled is True
    assert result.linked_oauth_providers == ["GITHUB", "GOOGLE"]


def test_current_identity_of_the_platform_admin_has_no_tenant_and_no_factors():
    uow = InMemoryUnitOfWork()
    admin = uow.agents.save(Agent.create("Root", "root@platform.test", role=AgentRole.ADMIN))
    uow.mfa.items[admin.id.value] = AgentMfa(admin.id.value, "ciphertext")  # pending, not enabled

    result = CurrentIdentityUseCase(uow).execute(admin)

    assert (result.tenant_name, result.mfa_enabled, result.linked_oauth_providers) == (None, False, [])
