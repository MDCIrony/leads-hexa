from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from tests.tokens import jwks, mint_token

_SETTINGS = Settings(
    database_url="postgresql://u:p@host:5432/db",
    jwks_url="http://jwks.invalid/internal/v1/jwks",
)


def test_stateless_adapters_are_shared_across_the_container_lifetime():
    """A fresh instance on every access would still be correct today (the
    assignment engine keeps no state of its own), but every other adapter
    listed here is shared for real reasons, so the container keeps treating
    all of them the same way."""
    container = Container(_SETTINGS)

    assert container.assignment_engine is container.assignment_engine
    assert container.token_verifier is container.token_verifier


def test_unit_of_work_is_built_fresh_on_every_call():
    """A unit of work owns one transaction; sharing it across requests would
    leak state between unrelated callers."""
    container = Container(_SETTINGS)

    assert container.unit_of_work() is not container.unit_of_work()


def test_bearers_verify_against_the_keys_identity_publishes():
    """The verifier reads whatever the JWKS fetch returns: identity's endpoint
    in the stack, the test keys here. Building the container fetches nothing."""
    fetched = []

    def fetch() -> dict:
        fetched.append(True)
        return jwks()

    container = Container(_SETTINGS, jwks_fetch=fetch)
    assert fetched == []

    assert container.token_verifier.verify(mint_token(role="ADMIN")).role == "ADMIN"
    assert fetched == [True]


def test_the_advisor_directory_asks_identity_for_a_token_meant_for_identity():
    """The e2e suite replaces the HTTP adapter, so this is what pins its wiring."""
    from dataclasses import replace

    container = Container(replace(_SETTINGS, identity_url="http://identity.test/", service_client_secret="s"))
    identity = container.advisor_directory._identity

    assert identity._url == "http://identity.test/internal/v1/agents/"
    assert (identity._tokens._url, identity._tokens._client_id, identity._tokens._audience) == (
        "http://identity.test/internal/v1/service-tokens", "lead-core", "identity")
    container.close()
