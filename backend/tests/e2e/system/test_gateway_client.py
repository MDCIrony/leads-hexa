"""GatewayClient must reproduce the gateway's trust rules, or every e2e test
that rides it proves nothing about the real stack (ADR-0031)."""
import uuid

from tests.e2e.helpers.auth_helpers import integration_headers, manager_headers, seed_agent
from tests.e2e.helpers.gateway_client import GatewayClient
from infrastructure.main import app
from tests.tokens import mint_token

_UNAUTHORIZED = {"error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"}


def _signed_manager_bearer() -> dict:
    # Signed with the very key the app trusts: only the gateway may put it there.
    return {"Authorization": f"Bearer {mint_token(uuid.uuid4(), uuid.uuid4(), 'MANAGER')}"}


def test_a_bearer_sent_by_the_caller_is_never_trusted():
    with GatewayClient(app) as client:
        response = client.get("/api/v1/leads", headers=_signed_manager_bearer())

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED


def test_the_session_decides_even_when_the_caller_sends_a_manager_bearer():
    with GatewayClient(app) as client:
        sales, _ = seed_agent(uuid.uuid4())

        response = client.get("/api/v1/leads", headers={**sales, **_signed_manager_bearer()})

    assert response.status_code == 403


def test_an_integration_key_reaches_the_integration_route():
    with GatewayClient(app) as client:
        response = client.get("/api/v1/leads", headers=integration_headers(uuid.uuid4()))

    assert response.status_code == 200


def test_internal_routes_do_not_exist_from_outside():
    with GatewayClient(app) as client:
        response = client.get("/internal/v1/jwks")

    assert response.status_code == 404
    assert response.json() == {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}


def test_a_public_route_never_sees_a_client_bearer_or_api_key():
    with GatewayClient(app) as client:
        response = client.get("/health", headers={**_signed_manager_bearer(), "X-Api-Key": "x.y"})

    assert response.status_code == 200
    assert "authorization" not in response.request.headers
    assert "x-api-key" not in response.request.headers


def test_a_forwarded_request_carries_only_the_gateway_bearer():
    with GatewayClient(app) as client:
        response = client.get(
            "/api/v1/leads",
            headers={**manager_headers(uuid.uuid4()), "Authorization": "Bearer forged", "X-Api-Key": "x.y"},
            cookies={"leads_session": "opaque"},
        )
        sent = response.request.headers

    assert response.status_code == 200
    assert sent["authorization"].startswith("Bearer ") and sent["authorization"] != "Bearer forged"
    assert "leads_session" not in sent.get("cookie", "")
    assert "x-api-key" not in sent


def test_paths_outside_the_api_do_not_reach_the_app():
    with GatewayClient(app) as client:
        response = client.get("/not-a-route")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_an_integration_key_is_refused_on_a_route_that_is_not_the_integration_one():
    with GatewayClient(app) as client:
        key = integration_headers(uuid.uuid4())

        created = client.post("/api/v1/groups", headers=key, json={"name": "X"})
        mine = client.get("/api/v1/leads/mine", headers=key)

    for response in (created, mine):
        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"
