import uuid
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from application.ports.output.oauth_identity_provider_port import OAuthIdentity
from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.config.settings import OAuthProviderSettings, Settings
from infrastructure.main import app


class _GoogleProvider:
    def __init__(self, email: str) -> None:
        self.email = email
        self.calls: list[tuple[str, str]] = []

    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        self.calls.append((code, pkce_verifier))
        return OAuthIdentity("google-subject", self.email, True, "OAuth HTTP")


def _seed_agent(client: TestClient) -> Agent:
    agent = Agent.create(
        "OAuth HTTP", f"oauth_{uuid.uuid4().hex[:8]}@test.com", role=AgentRole.MANAGER,
        tenant_id=uuid.uuid4(),
    )
    with PostgresUnitOfWork(client.app.state.container.database) as uow:
        uow.agents.save(agent)
    return agent


def test_oauth_callback_consumes_browser_challenge_before_creating_an_opaque_session(monkeypatch):
    with TestClient(app) as client:
        agent = _seed_agent(client)
        container = client.app.state.container
        provider = _GoogleProvider(agent.email)
        current = container.settings
        monkeypatch.setattr(container, "_settings", Settings(
            database_url=current.database_url, mfa_encryption_key=current.mfa_encryption_key,
            cors_origins=list(current.cors_origins), frontend_origin="http://localhost",
            google_oauth=OAuthProviderSettings("client-id", "client-secret", "http://localhost:8001/api/v1/auth/oauth/google/callback"),
        ))
        monkeypatch.setattr(container, "_oauth_identity_providers", {"GOOGLE": provider})

        start = client.get("/api/v1/auth/oauth/google/start?return_path=/mis-leads", follow_redirects=False)
        query = parse_qs(urlsplit(start.headers["location"]).query)
        callback = client.get(
            f"/api/v1/auth/oauth/google/callback?code=provider-code&state={query['state'][0]}",
            follow_redirects=False,
        )
        me = client.get("/api/v1/auth/me")
        replay = client.get(
            f"/api/v1/auth/oauth/google/callback?code=provider-code&state={query['state'][0]}",
            follow_redirects=False,
        )

    assert start.status_code == 303
    assert query["code_challenge_method"] == ["S256"]
    assert "leads_oauth_challenge=" in start.headers["set-cookie"]
    assert "Path=/api/v1/auth/oauth" in start.headers["set-cookie"]
    assert callback.status_code == 303
    assert callback.headers["location"] == "http://localhost/mis-leads"
    assert "leads_session=" in callback.headers["set-cookie"]
    assert me.json()["linked_oauth_providers"] == ["GOOGLE"]
    assert provider.calls == [("provider-code", provider.calls[0][1])]
    assert replay.headers["location"] == "http://localhost/login?oauth_error=1"
    assert "provider-code" not in replay.headers["location"]
