from uuid import uuid4

from tests.e2e.tokens import FOREIGN_SIGNER, bearer, mint_token

URL = "/api/v1/notifications"


def test_lists_only_the_callers_notifications(client, auth, agent_id, seed):
    seed(agent_id, 2)
    seed(uuid4(), 1)

    response = client.get(URL, headers=auth)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert data["unread_count"] == 2
    assert {item["message"] for item in data["items"]} == {"Notice 0", "Notice 1"}
    assert set(data["items"][0]) == {
        "id", "kind", "message", "lead_id", "intake_record_id", "is_read", "created_at",
    }


def test_unread_count_ignores_the_page_and_has_more_is_correct(client, auth, agent_id, seed):
    seed(agent_id, 3)

    first = client.get(f"{URL}?limit=1", headers=auth).json()
    last = client.get(f"{URL}?limit=1&offset=2", headers=auth).json()

    assert len(first["items"]) == 1
    assert first["total"] == 3
    assert first["unread_count"] == 3
    assert first["has_more"] is True
    assert last["has_more"] is False


def test_trailing_slash_is_served_without_redirect(client, auth):
    assert client.get(f"{URL}/", headers=auth, follow_redirects=False).status_code == 200


def test_marking_own_notification_returns_204_and_leaves_it_read(client, auth, agent_id, seed):
    notice = seed(agent_id, 2)[0]

    response = client.post(f"{URL}/{notice.id}/read", headers=auth)

    assert response.status_code == 204, response.text
    data = client.get(f"{URL}?unread_only=true", headers=auth).json()
    assert data["total"] == 1
    assert data["unread_count"] == 1


def test_marking_anothers_notification_is_404_not_403(client, auth, seed):
    notice = seed(uuid4())[0]

    response = client.post(f"{URL}/{notice.id}/read", headers=auth)

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOTIFICATION_NOT_FOUND"


def test_read_all_returns_204_and_zeroes_the_counter(client, auth, agent_id, seed):
    seed(agent_id, 3)

    assert client.post(f"{URL}/read-all", headers=auth).status_code == 204
    assert client.get(URL, headers=auth).json()["unread_count"] == 0


def test_missing_bearer_is_401(client):
    response = client.get(URL)

    assert response.status_code == 401
    assert response.json() == {
        "error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required",
    }


def test_integration_token_is_401(client, tenant_id):
    token = mint_token(tenant_id=tenant_id, role="INTEGRATION", ptype="integration")

    assert client.get(URL, headers=bearer(token)).status_code == 401


def test_admin_without_organization_is_403(client):
    response = client.get(URL, headers=bearer(mint_token(role="ADMIN")))

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_token_signed_with_another_key_is_401(client, tenant_id):
    token = mint_token(tenant_id=tenant_id, signer=FOREIGN_SIGNER)

    assert client.get(URL, headers=bearer(token)).status_code == 401


def test_non_uuid_subject_is_401(client, tenant_id):
    token = mint_token("not-a-uuid", tenant_id)

    assert client.get(URL, headers=bearer(token)).status_code == 401


def test_unreachable_jwks_is_503(client_without_keys, tenant_id):
    response = client_without_keys.get(URL, headers=bearer(mint_token(tenant_id=tenant_id)))

    assert response.status_code == 503
    assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"


def test_invalid_limit_is_422_with_the_error_envelope(client, auth):
    response = client.get(f"{URL}?limit=0", headers=auth)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] is True
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["details"][0]["field"] == "limit"


def test_request_id_is_returned_and_echoed(client, auth):
    assert client.get(URL, headers=auth).headers["x-request-id"]
    echoed = client.get(URL, headers={**auth, "X-Request-Id": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"


def test_health_runs_the_lifespan_against_the_test_database(test_db):
    from fastapi.testclient import TestClient

    from infrastructure.main import app

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
