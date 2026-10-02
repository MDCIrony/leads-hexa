import pytest
from fastapi.testclient import TestClient

from infrastructure.adapters.input.api.dependencies import get_container
from infrastructure.config.settings import ApiSettings
from infrastructure.di.container import Container
from infrastructure.main import app
from tests.tokens import FOREIGN_SIGNER, bearer, jwks, mint_token

_SETTINGS = ApiSettings(
    database_url="postgresql://u:p@nowhere:5432/db", jwks_url="http://identity/jwks",
    lead_core_url="http://lead-core", service_client_secret="s3cret",
)
_ID = "00000000-0000-4000-8000-000000000001"
# Every route of the public API: authorization is decided before any use case runs,
# so none of them needs a database to answer 401 or 403.
_ROUTES = [
    ("GET", "/api/v1/sources"),
    ("POST", "/api/v1/sources"),
    ("PATCH", f"/api/v1/sources/{_ID}"),
    ("DELETE", f"/api/v1/sources/{_ID}"),
    ("POST", "/api/v1/intake/leads/ingest"),
    ("POST", "/api/v1/intake/leads/batch-upload"),
    ("GET", "/api/v1/intake/records"),
    ("POST", f"/api/v1/intake/records/{_ID}/promote"),
    ("POST", f"/api/v1/intake/records/{_ID}/discard"),
    ("GET", "/api/v1/intake/jobs"),
    ("GET", f"/api/v1/intake/jobs/{_ID}"),
    ("POST", f"/api/v1/intake/jobs/{_ID}/reprocess"),
    ("GET", "/api/v1/intake/stats"),
]
_TENANT = "00000000-0000-4000-8000-0000000000aa"


@pytest.fixture
def make_client():
    """Builds clients over containers that are closed, and the override removed, afterwards."""
    containers = []

    def _make(jwks_fetch=jwks) -> TestClient:
        container = Container(_SETTINGS, jwks_fetch=jwks_fetch)
        containers.append(container)
        app.dependency_overrides[get_container] = lambda: container
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
    for container in containers:
        container.close()


@pytest.mark.parametrize(("method", "path"), _ROUTES)
def test_no_bearer_is_401(method, path, make_client):
    response = make_client().request(method, path)

    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(("method", "path"), _ROUTES)
@pytest.mark.parametrize("role", ["AGENT", "ADMIN"])
def test_a_role_that_does_not_manage_an_organization_is_403(method, path, role, make_client):
    token = mint_token(tenant_id=None if role == "ADMIN" else _TENANT, role=role)

    response = make_client().request(method, path, headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_a_manager_without_an_organization_is_403(make_client):
    response = make_client().get("/api/v1/sources", headers=bearer(mint_token(role="MANAGER")))

    assert response.status_code == 403


def test_an_integration_credential_is_401(make_client):
    token = mint_token(tenant_id=_TENANT, role="INTEGRATION", ptype="integration")

    assert make_client().get("/api/v1/intake/records", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("headers", [
    {"Authorization": "Basic abc"},
    {"Authorization": "Bearer "},
    {"Authorization": "Bearer not-a-jwt"},
    bearer(mint_token(tenant_id=_TENANT, signer=FOREIGN_SIGNER)),
])
def test_an_unusable_bearer_is_401(headers, make_client):
    assert make_client().get("/api/v1/sources", headers=headers).status_code == 401


def test_unreachable_signing_keys_are_503_not_401(make_client):
    def unreachable() -> dict:
        raise ConnectionError("jwks endpoint is down")

    response = make_client(unreachable).get("/api/v1/sources", headers=bearer(mint_token(tenant_id=_TENANT)))

    assert response.status_code == 503
    assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"


def test_the_openapi_document_publishes_every_route_for_the_gateway():
    document = TestClient(app).get("/openapi.json").json()

    published = {(method.upper(), path) for path, item in document["paths"].items() for method in item}

    assert published == {
        ("GET", "/api/v1/sources"), ("POST", "/api/v1/sources"),
        ("PATCH", "/api/v1/sources/{source_id}"), ("DELETE", "/api/v1/sources/{source_id}"),
        ("POST", "/api/v1/intake/leads/ingest"), ("POST", "/api/v1/intake/leads/batch-upload"),
        ("GET", "/api/v1/intake/records"),
        ("POST", "/api/v1/intake/records/{record_id}/promote"),
        ("POST", "/api/v1/intake/records/{record_id}/discard"),
        ("GET", "/api/v1/intake/jobs"), ("GET", "/api/v1/intake/jobs/{job_id}"),
        ("POST", "/api/v1/intake/jobs/{job_id}/reprocess"),
        ("GET", "/api/v1/intake/stats"), ("GET", "/health"),
    }
