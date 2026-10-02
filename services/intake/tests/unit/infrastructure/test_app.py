from fastapi.testclient import TestClient

from infrastructure.adapters.input.api.exception_handlers import STATUS_BY_ERROR_CODE
from infrastructure.main import app

# No `with`: the lifespan would open the database, and this is a unit test.
_client = TestClient(app)


def test_health_answers_and_every_response_carries_a_request_id():
    response = _client.get("/health", headers={"x-request-id": "req-1"})

    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "req-1"


def test_an_unknown_route_uses_the_error_envelope():
    response = _client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_intake_error_codes_map_to_their_statuses():
    assert {code: STATUS_BY_ERROR_CODE[code] for code in (
        "SOURCE_NOT_FOUND", "INTAKE_RECORD_NOT_FOUND", "INTAKE_JOB_NOT_FOUND",
        "PAYLOAD_TOO_LARGE", "LEAD_CORE_UNAVAILABLE",
    )} == {
        "SOURCE_NOT_FOUND": 404, "INTAKE_RECORD_NOT_FOUND": 404, "INTAKE_JOB_NOT_FOUND": 404,
        "PAYLOAD_TOO_LARGE": 413, "LEAD_CORE_UNAVAILABLE": 503,
    }
