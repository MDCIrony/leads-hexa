import hashlib
from dataclasses import replace

import pytest
from chassis.auth import TokenError

from domain.agents.agent import Agent
from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.output.oauth.providers import (
    GitHubOAuthIdentityProvider, GoogleOAuthIdentityProvider, TestOAuthIdentityProvider,
)
from infrastructure.config.oauth import TEST_GOOGLE_OAUTH, OAuthProviderSettings
from infrastructure.config.settings import ApiSettings
from infrastructure.di.container import Container
from infrastructure.security.service_clients import parse_service_clients

_SECRET = "core-secret"
_SETTINGS = ApiSettings(
    database_url="postgresql://u:p@host:5432/db",
    signing_keys="unit-1=We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk,unit-0=_tS3Kljdu1EaOrOFVqdVQ2G1VaP7q5pWZKmqPb9W-mU",
    service_clients=parse_service_clients(f"lead-core:identity:{hashlib.sha256(_SECRET.encode()).hexdigest()}"),
    mfa_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
)
_GITHUB = OAuthProviderSettings("id", "secret", "https://a.test/oauth/github")


def test_unit_of_work_is_built_fresh_on_every_call():
    container = Container(_SETTINGS)

    assert container.unit_of_work() is not container.unit_of_work()


def test_publishes_every_key_public_only_and_signs_with_the_first():
    container = Container(_SETTINGS)
    token = container.token_issuer.issue(Agent.create("A", "a@a.invalid", role=AgentRole.ADMIN), "human")

    assert [key["kid"] for key in container.jwks["keys"]] == ["unit-1", "unit-0"]
    assert all("d" not in key for key in container.jwks["keys"])
    assert container.token_verifier.verify(token).role == "ADMIN"


def test_service_tokens_open_identity_and_human_tokens_do_not():
    container = Container(_SETTINGS)
    service = container.service_token_issuer.issue("lead-core", _SECRET, "identity")
    human = container.token_issuer.issue(Agent.create("A", "a@a.invalid", role=AgentRole.ADMIN), "human")

    assert container.service_token_verifier.verify(service, {"lead-core"}).sub == "lead-core"
    with pytest.raises(TokenError):
        container.service_token_verifier.verify(human, {"lead-core"})


def test_only_enabled_providers_are_offered():
    assert Container(_SETTINGS).oauth_providers == {}

    providers = Container(replace(_SETTINGS, github_oauth=_GITHUB)).oauth_providers
    assert list(providers) == ["GITHUB"] and isinstance(providers["GITHUB"], GitHubOAuthIdentityProvider)

    google = OAuthProviderSettings("id", "secret", "https://a.test/oauth/google")
    assert isinstance(Container(replace(_SETTINGS, google_oauth=google)).oauth_providers["GOOGLE"],
                      GoogleOAuthIdentityProvider)


def test_the_deterministic_provider_replaces_google_only_in_oauth_test_mode():
    settings = replace(_SETTINGS, oauth_test_mode=True, google_oauth=TEST_GOOGLE_OAUTH, github_oauth=_GITHUB)

    providers = Container(settings).oauth_providers

    assert isinstance(providers["GOOGLE"], TestOAuthIdentityProvider)
    assert isinstance(providers["GITHUB"], GitHubOAuthIdentityProvider)
