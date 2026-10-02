import hashlib

import pytest

from infrastructure.security.service_clients import ServiceClients, parse_service_clients

_INTAKE_SECRET = "intake-secret"
_CORE_SECRET = "core-secret"


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


_SPEC = f"intake:lead-core:{_digest(_INTAKE_SECRET)}, lead-core:identity|intake:{_digest(_CORE_SECRET).upper()}"


def test_parses_every_client_with_its_audiences():
    clients = parse_service_clients(_SPEC)

    assert [(c.client_id, c.audiences) for c in clients] == [
        ("intake", {"lead-core"}),
        ("lead-core", {"identity", "intake"}),
    ]
    assert clients[1].secret_sha256 == hashlib.sha256(_CORE_SECRET.encode()).digest()


@pytest.mark.parametrize("spec", [
    "", " , ",
    "intake:lead-core",
    f"intake:lead-core:{_digest('x')}:extra",
    f":lead-core:{_digest('x')}",
    f"intake::{_digest('x')}",
    f"intake:lead-core|:{_digest('x')}",
    "intake:lead-core:not-hex",
    f"intake:lead-core:{_digest('x')[:63]}",
    f"intake:lead-core:{_digest('x')},intake:identity:{_digest('y')}",
])
def test_a_malformed_spec_is_refused_without_echoing_any_digest(spec):
    with pytest.raises(ValueError, match="SERVICE_CLIENTS") as raised:
        parse_service_clients(spec)

    assert _digest("x")[:16] not in str(raised.value)
    assert _digest("y")[:16] not in str(raised.value)


@pytest.fixture
def clients():
    return ServiceClients(parse_service_clients(_SPEC))


def test_a_known_client_with_its_secret_and_an_allowed_audience_authenticates(clients):
    assert clients.authenticate("intake", _INTAKE_SECRET, "lead-core") is True
    assert clients.authenticate("lead-core", _CORE_SECRET, "intake") is True


@pytest.mark.parametrize("client_id,secret,audience", [
    ("intake", "wrong", "lead-core"),
    ("intake", _CORE_SECRET, "lead-core"),
    ("intake", _INTAKE_SECRET, "identity"),
    ("unknown", _INTAKE_SECRET, "lead-core"),
    ("unknown", "", "lead-core"),
    ("intake", "", "lead-core"),
])
def test_anything_else_is_refused(clients, client_id, secret, audience):
    assert clients.authenticate(client_id, secret, audience) is False
