from urllib.parse import parse_qs

import httpx

from infrastructure.adapters.output.http import oauth_identity_providers
from infrastructure.adapters.output.http.oauth_identity_providers import GitHubOAuthIdentityProvider
from infrastructure.config.settings import OAuthProviderSettings


def test_github_exchanges_pkce_and_uses_only_the_verified_primary_email(monkeypatch):
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "github-token"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 123, "name": "GitHub User"})
        return httpx.Response(200, json=[
            {"email": "unverified@example.test", "primary": True, "verified": False},
            {"email": "secondary@example.test", "primary": False, "verified": True},
            {"email": "primary@example.test", "primary": True, "verified": True},
        ])

    real_client = httpx.Client
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        oauth_identity_providers.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    provider = GitHubOAuthIdentityProvider(OAuthProviderSettings(
        "client-id", "client-secret", "http://localhost/callback",
    ))

    identity = provider.exchange("authorization-code", "pkce-verifier")

    token_form = parse_qs(requests[0].content.decode())
    assert token_form["code_verifier"] == ["pkce-verifier"]
    assert token_form["redirect_uri"] == ["http://localhost/callback"]
    assert [request.url.path for request in requests] == [
        "/login/oauth/access_token", "/user", "/user/emails",
    ]
    assert identity.provider_subject == "123"
    assert identity.email == "primary@example.test"
    assert identity.email_verified is True
    assert identity.name == "GitHub User"
