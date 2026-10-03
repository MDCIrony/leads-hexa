import uuid

from tests.e2e.helpers.gateway_client import GatewayClient

from infrastructure.main import app
from test_lead_endpoints import _manager_auth_headers

_REQUIRED_KEYS = {"error", "error_code", "message"}


def test_validation_errors_use_the_common_envelope():
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(str(uuid.uuid4()))
        response = client.post("/api/v1/groups", json={}, headers=headers)
    assert response.status_code == 422
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)


def test_missing_credentials_use_the_common_envelope():
    with GatewayClient(app) as client:
        response = client.get("/api/v1/leads")
    assert response.status_code == 401
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "UNAUTHORIZED"


def test_unknown_route_uses_the_common_envelope():
    # Authenticated, as the gateway only forwards a session it resolved.
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(str(uuid.uuid4()))
        response = client.get("/api/v1/does-not-exist", headers=headers)
    assert response.status_code == 404
    assert _REQUIRED_KEYS <= set(response.json())


def test_negative_limit_is_a_validation_error_not_a_500():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?limit=-5", headers=headers)
        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert any(detail["field"] == "limit" for detail in body["details"])


def test_negative_offset_is_a_validation_error_not_a_500():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?offset=-10", headers=headers)
        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert any(detail["field"] == "offset" for detail in body["details"])


def test_limit_above_the_ceiling_is_a_validation_error():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?limit=5000", headers=headers)
        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_valid_pagination_still_works():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?limit=10&offset=0", headers=headers)
        assert response.status_code == 200
