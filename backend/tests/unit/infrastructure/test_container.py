from infrastructure.config.settings import Settings
from infrastructure.di.container import Container

_SETTINGS = Settings(
    database_url="postgresql://u:p@host:5432/db",
    mfa_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    signing_keys="unit-1=We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk",
)


def test_stateless_adapters_are_shared_across_the_container_lifetime():
    """A fresh instance on every access would still be correct today (the
    assignment engine keeps no state of its own), but every other adapter
    listed here is shared for real reasons, so the container keeps treating
    all of them the same way."""
    container = Container(_SETTINGS)

    assert container.assignment_engine is container.assignment_engine
    assert container.password_hasher is container.password_hasher


def test_unit_of_work_is_built_fresh_on_every_call():
    """A unit of work owns one transaction; sharing it across requests would
    leak state between unrelated callers."""
    container = Container(_SETTINGS)

    assert container.unit_of_work() is not container.unit_of_work()


def test_issued_tokens_verify_against_the_published_keys():
    """F0 wiring: the verifier reads the container's own JWKS, so a token it
    issues must verify and the published keys must be public-only."""
    from domain.entities.agent import Agent
    from domain.value_objects.enums import AgentRole

    container = Container(_SETTINGS)
    token = container.token_issuer.issue(Agent.create("A", "a@a.invalid", role=AgentRole.ADMIN), "human")

    assert container.token_verifier.verify(token).role == "ADMIN"
    assert [key["kid"] for key in container.jwks["keys"]] == ["unit-1"]
    assert all("d" not in key for key in container.jwks["keys"])


def test_the_advisor_directory_asks_identity_for_a_token_meant_for_identity():
    """The e2e suite replaces the HTTP adapter, so this is what pins its wiring."""
    from dataclasses import replace

    container = Container(replace(_SETTINGS, identity_url="http://identity.test/", service_client_secret="s"))
    identity = container.advisor_directory._identity

    assert identity._url == "http://identity.test/internal/v1/agents/"
    assert (identity._tokens._url, identity._tokens._client_id, identity._tokens._audience) == (
        "http://identity.test/internal/v1/service-tokens", "lead-core", "identity")
    container.close()
