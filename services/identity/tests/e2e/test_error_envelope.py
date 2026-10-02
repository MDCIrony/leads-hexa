from tests.e2e.seeds import bootstrap_admin, create_organization

_REQUIRED_KEYS = {"error", "error_code", "message"}


def test_validation_errors_use_the_common_envelope(client):
    response = client.post("/api/v1/auth/login", data={"username": "only-this"})

    assert response.status_code == 422
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["details"] == [{"field": "password", "code": "missing", "message": "Field required"}]


def test_missing_credentials_use_the_common_envelope(client):
    response = client.get("/api/v1/agents")

    assert response.status_code == 401
    assert _REQUIRED_KEYS <= set(response.json())
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_unknown_route_and_method_use_the_common_envelope(direct):
    unknown = direct.get("/api/v1/does-not-exist")
    method = direct.put("/api/v1/auth/me")

    assert (unknown.status_code, unknown.json()["error_code"]) == (404, "NOT_FOUND")
    assert (method.status_code, method.json()["error_code"]) == (405, "METHOD_NOT_ALLOWED")
    assert _REQUIRED_KEYS <= set(unknown.json()) and _REQUIRED_KEYS <= set(method.json())


def test_pagination_bounds_are_validation_errors_not_500s(client):
    _, headers = create_organization(client, bootstrap_admin(client))

    for query, field in (("limit=-5", "limit"), ("offset=-10", "offset"), ("limit=5000", "limit")):
        response = client.get(f"/api/v1/agents?{query}", headers=headers)
        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"
        assert any(detail["field"] == field for detail in response.json()["details"])
    assert client.get("/api/v1/agents?limit=10&offset=0", headers=headers).status_code == 200


def test_a_malformed_identifier_is_a_validation_error(client):
    _, headers = create_organization(client, bootstrap_admin(client))

    response = client.get("/api/v1/agents/not-a-uuid", headers=headers)

    assert (response.status_code, response.json()["error_code"]) == (422, "VALIDATION_ERROR")
