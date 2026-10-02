import dataclasses
from urllib.parse import parse_qs, urlsplit

from application.ports.output.social import OAuthIdentity
from infrastructure.config.oauth import OAuthProviderSettings
from tests.e2e.seeds import seed_agent


class _GoogleProvider:
    def __init__(self, email: str) -> None:
        self.email = email
        self.calls: list[tuple[str, str]] = []

    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        self.calls.append((code, pkce_verifier))
        return OAuthIdentity("google-subject", self.email, True, "OAuth HTTP")


def _configure_google(client, monkeypatch, provider) -> None:
    container = client.app.state.container
    google = OAuthProviderSettings("client-id", "client-secret", "http://localhost/api/v1/auth/oauth/google/callback")
    monkeypatch.setattr(container, "settings", dataclasses.replace(
        container.settings, frontend_origin="http://localhost", google_oauth=google,
    ))
    monkeypatch.setattr(container, "oauth_providers", {"GOOGLE": provider})


def test_oauth_callback_consumes_browser_challenge_before_creating_an_opaque_session(client, monkeypatch):
    agent = seed_agent(client, hashed_password=None)
    provider = _GoogleProvider(agent.email)
    _configure_google(client, monkeypatch, provider)

    providers = client.get("/api/v1/auth/oauth/providers")
    start = client.get("/api/v1/auth/oauth/google/start?return_path=/mis-leads", follow_redirects=False)
    query = parse_qs(urlsplit(start.headers["location"]).query)
    callback = client.get(
        f"/api/v1/auth/oauth/google/callback?code=provider-code&state={query['state'][0]}", follow_redirects=False,
    )
    me = client.get("/api/v1/auth/me")
    replay = client.get(
        f"/api/v1/auth/oauth/google/callback?code=provider-code&state={query['state'][0]}", follow_redirects=False,
    )

    assert providers.json() == {"providers": ["GOOGLE"]}
    assert providers.headers["cache-control"] == "no-store"
    assert start.status_code == 303
    assert start.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["code_challenge_method"] == ["S256"]
    assert query["client_id"] == ["client-id"]
    assert "leads_oauth_challenge=" in start.headers["set-cookie"]
    assert "Path=/api/v1/auth/oauth" in start.headers["set-cookie"]
    assert callback.status_code == 303
    assert callback.headers["location"] == "http://localhost/mis-leads"
    assert "leads_session=" in callback.headers["set-cookie"]
    assert me.json()["linked_oauth_providers"] == ["GOOGLE"]
    assert provider.calls == [("provider-code", provider.calls[0][1])]
    assert replay.headers["location"] == "http://localhost/login?oauth_error=1"
    assert "provider-code" not in replay.headers["location"]


def test_an_unconfigured_provider_is_not_found_and_its_callback_fails_generically(client, monkeypatch):
    monkeypatch.setattr(client.app.state.container, "oauth_providers", {})

    start = client.get("/api/v1/auth/oauth/github/start", follow_redirects=False)
    unknown = client.get("/api/v1/auth/oauth/myspace/start", follow_redirects=False)
    callback = client.get("/api/v1/auth/oauth/github/callback?code=x&state=y", follow_redirects=False)

    assert (start.status_code, start.json()["error_code"]) == (404, "NOT_FOUND")
    assert unknown.status_code == 404
    assert callback.status_code == 303
    assert callback.headers["location"].endswith("/login?oauth_error=1")


def test_an_external_return_path_is_rejected(client, monkeypatch):
    _configure_google(client, monkeypatch, _GoogleProvider("x@x.test"))

    response = client.get("/api/v1/auth/oauth/google/start?return_path=https://evil.test/", follow_redirects=False)

    assert (response.status_code, response.json()["message"]) == (400, "Ruta de retorno inválida")
