"""/internal/v1/admissions over HTTP, as intake calls it (contracts/openapi/lead-core-internal.v1.yaml).

Plain TestClient, not GatewayClient: the gateway 404s /internal/, and intake
reaches lead-core inside the Compose network with its own service token."""
import uuid
from types import SimpleNamespace

import pytest
from chassis.auth import KeysUnavailable
from chassis.testing.contracts import assert_conforms, load_fixture
from fastapi.testclient import TestClient

from domain.exceptions import DomainException
from infrastructure.adapters.input.internal.admissions_router import require_service_caller
from infrastructure.main import app
from tests.tokens import mint_service_token, mint_token

_URL = "/internal/v1/admissions"


def _as(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _request(**candidate) -> dict:
    body = {"tenant_id": str(uuid.uuid4()), "intake_record_id": str(uuid.uuid4()), "source_id": str(uuid.uuid4()),
            "candidate": {"first_name": "Ana", "last_name": "Diaz", "email": "ana@x.test", "phone": "600",
                          "company": "Acme", "industry": "tech", "budget": "9000.00", "custom_attributes": {}}}
    body["candidate"].update(candidate)
    return body


def _outbox_rows(database) -> int:
    with database.get_connection(autocommit=True) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM outbox_events").fetchone()["n"]


# Callables, minted when the test runs: a token minted at collection could
# expire before a long suite reaches it.
@pytest.mark.parametrize("headers_of", [
    lambda: {},
    lambda: {"Authorization": "Basic abc"},
    lambda: _as("not-a-jwt"),
    lambda: _as(mint_token(tenant_id=uuid.uuid4())),
    lambda: _as(mint_service_token(sub="lead-core")),
    lambda: _as(mint_service_token(audience="identity")),
], ids=["none", "not-bearer", "garbage", "human", "other-caller", "other-audience"])
def test_anything_but_intakes_service_token_is_one_401(test_db, headers_of):
    headers = headers_of()
    with TestClient(app) as client:
        response = client.post(_URL, json=_request(), headers=headers)
        listed = client.get(_URL, params={"intake_record_ids": str(uuid.uuid4())}, headers=headers)

    assert (response.status_code, response.json()["error_code"]) == (401, "UNAUTHORIZED")
    assert listed.status_code == 401


def test_an_admission_conforms_and_repeating_it_returns_the_same_lead_without_publishing(test_db):
    body = _request()
    with TestClient(app) as client:
        first = client.post(_URL, json=body, headers=_as(mint_service_token()))
        rows = _outbox_rows(test_db)
        again = client.post(_URL, json=body, headers=_as(mint_service_token()))

    assert first.status_code == 200, first.text
    assert_conforms(first.json(), "schemas/lead-core/admission-result.v1.schema.json")
    assert first.json()["outcome"] == "ADMITTED"
    assert again.json() == first.json()
    assert _outbox_rows(test_db) == rows


def test_the_contract_fixture_is_accepted(test_db):
    with TestClient(app) as client:
        response = client.post(_URL, json=load_fixture("lead-core/admission-request.v1.json"),
                               headers=_as(mint_service_token()))

    assert response.status_code == 200, response.text
    assert_conforms(response.json(), "schemas/lead-core/admission-result.v1.schema.json")


def test_an_unreadable_budget_is_a_rejection_that_conforms_not_a_422(test_db):
    with TestClient(app) as client:
        response = client.post(_URL, json=_request(budget="nine thousand"), headers=_as(mint_service_token()))

    assert response.status_code == 200, response.text
    assert_conforms(response.json(), "schemas/lead-core/admission-result.v1.schema.json")
    assert [e["error_code"] for e in response.json()["errors"]] == ["INVALID_BUDGET"]


def test_a_body_without_the_contracts_shape_is_a_422(test_db):
    with TestClient(app) as client:
        response = client.post(_URL, json=_request(budget=9000.5), headers=_as(mint_service_token()))

    assert response.status_code == 422


def test_the_lookup_answers_the_known_records_only(test_db):
    body = _request()
    with TestClient(app) as client:
        admitted = client.post(_URL, json=body, headers=_as(mint_service_token())).json()
        listed = client.get(_URL, params={"intake_record_ids": [body["intake_record_id"], str(uuid.uuid4())]},
                            headers=_as(mint_service_token()))

    assert listed.status_code == 200, listed.text
    assert_conforms(listed.json(), "schemas/lead-core/admission-lookup.v1.schema.json")
    assert listed.json()["items"] == [{"intake_record_id": body["intake_record_id"], "tenant_id": body["tenant_id"],
                                       "lead_id": admitted["lead_id"]}]


@pytest.mark.parametrize("ids", [[], ["not-a-uuid"], [str(uuid.uuid4()) for _ in range(201)]],
                         ids=["none", "invalid", "over-200"])
def test_a_lookup_outside_one_to_two_hundred_valid_ids_is_a_422(test_db, ids):
    with TestClient(app) as client:
        response = client.get(_URL, params={"intake_record_ids": ids}, headers=_as(mint_service_token()))

    assert (response.status_code, response.json()["error_code"]) == (422, "VALIDATION_ERROR")


def test_unavailable_signing_keys_are_a_503_not_the_callers_fault():
    def verify(token, callers):
        raise KeysUnavailable("identity down")

    container = SimpleNamespace(service_token_verifier=SimpleNamespace(verify=verify))
    request = SimpleNamespace(headers={"authorization": "Bearer abc"})

    with pytest.raises(DomainException) as raised:
        require_service_caller(request, container)

    assert raised.value.error_code == "SERVICE_UNAVAILABLE"


def test_a_missing_required_field_is_a_rejection_not_a_400(test_db):
    with TestClient(app) as client:
        response = client.post(_URL, json=_request(last_name=None), headers=_as(mint_service_token()))

    assert response.status_code == 200, response.text
    assert_conforms(response.json(), "schemas/lead-core/admission-result.v1.schema.json")
    assert [(e["field"], e["error_code"]) for e in response.json()["errors"]] == [
        ("last_name", "MISSING_REQUIRED_FIELD")]
