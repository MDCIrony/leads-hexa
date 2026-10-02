"""HttpLeadAdmission against lead-core's admission contract: the fixtures of contracts/
served by an httpx.MockTransport, so a contract change breaks here."""
import json
from uuid import UUID

import httpx
import pytest
from chassis.testing.contracts import assert_conforms, load_fixture
from chassis.web import request_id_var

from application.dtos.admissions import AdmissionCandidate, AdmissionRequest
from application.ports.output.admissions import AdmissionUnavailable
from infrastructure.adapters.output.admissions.http_lead_admission import HttpLeadAdmission
from tests.unit.infrastructure.admissions.lead_core_double import TOKEN, LeadCore, client_for, respond

_REQUEST = load_fixture("lead-core/admission-request.v1.json")
_ADMITTED = load_fixture("lead-core/admission-result-admitted.v1.json")
_REJECTED = load_fixture("lead-core/admission-result-rejected.v1.json")


def _admission_request() -> AdmissionRequest:
    c = _REQUEST["candidate"]
    return AdmissionRequest(
        tenant_id=UUID(_REQUEST["tenant_id"]), intake_record_id=UUID(_REQUEST["intake_record_id"]),
        source_id=UUID(_REQUEST["source_id"]),
        candidate=AdmissionCandidate(
            c["first_name"], c["last_name"], c["email"], c["phone"], c["company"], c["industry"], c["budget"],
            c["custom_attributes"]),
    )


def _admit(lead_core: LeadCore):
    client, tokens = client_for(lead_core)
    return HttpLeadAdmission(client).admit(_admission_request()), tokens


def test_the_fixtures_conform_to_the_schemas():
    assert_conforms(_REQUEST, "schemas/lead-core/admission-request.v1.schema.json")
    assert_conforms(_ADMITTED, "schemas/lead-core/admission-result.v1.schema.json")
    assert_conforms(_REJECTED, "schemas/lead-core/admission-result.v1.schema.json")


def test_the_request_conforms_and_carries_a_service_token_for_lead_core():
    lead_core = LeadCore(respond(body=_ADMITTED))

    _admit(lead_core)

    [call] = lead_core.calls
    assert (call.method, call.url.path) == ("POST", "/internal/v1/admissions")
    assert call.headers["Authorization"] == f"Bearer {TOKEN['access_token']}"
    assert json.loads(call.content) == _REQUEST
    assert_conforms(json.loads(call.content), "schemas/lead-core/admission-request.v1.schema.json")
    assert lead_core.token_bodies() == [{"client_id": "intake", "client_secret": "secret", "audience": "lead-core"}]


def test_an_admitted_answer_maps_every_field():
    result, _ = _admit(LeadCore(respond(body=_ADMITTED)))

    assert (result.outcome, result.lead_id, result.status, result.score) == (
        "ADMITTED", _ADMITTED["lead_id"], _ADMITTED["status"], _ADMITTED["score"])
    assert (result.assigned_agent_id, result.applied_rules_count) == (
        _ADMITTED["assigned_agent_id"], _ADMITTED["applied_rules_count"])


def test_the_status_is_relayed_as_an_opaque_string():
    result, _ = _admit(LeadCore(respond(body={**_ADMITTED, "status": "SOMETHING_NEW"})))

    assert result.status == "SOMETHING_NEW"


def test_an_admitted_lead_without_an_agent_maps_to_none():
    result, _ = _admit(LeadCore(respond(body={**_ADMITTED, "assigned_agent_id": None})))

    assert result.assigned_agent_id is None


def test_a_rejected_answer_maps_the_errors():
    result, _ = _admit(LeadCore(respond(body=_REJECTED)))

    [error] = result.errors
    expected = _REJECTED["errors"][0]
    assert (result.outcome, error.field, error.message, error.error_code) == (
        "REJECTED", expected["field"], expected["message"], expected["error_code"])


def test_the_token_is_reused_across_admissions():
    lead_core = LeadCore(respond(body=_ADMITTED))
    client, _ = client_for(lead_core)
    adapter = HttpLeadAdmission(client)

    adapter.admit(_admission_request())
    adapter.admit(_admission_request())

    assert len(lead_core.token_requests) == 1


@pytest.mark.parametrize("lead_core", [
    LeadCore(fail=httpx.ConnectError("refused")),
    LeadCore(fail=httpx.ReadTimeout("slow")),
    LeadCore(respond(500, {"error": True})),
    LeadCore(respond(503, {"error": True})),
    LeadCore(respond(422, {"error": True})),
    LeadCore(respond(body=_ADMITTED), token_status=500),
    LeadCore(respond(content=b"<html>not json")),
    LeadCore(respond(body={"outcome": "MAYBE"})),
    LeadCore(respond(body={k: v for k, v in _ADMITTED.items() if k != "outcome"})),
    LeadCore(respond(body={**_ADMITTED, "lead_id": "not-a-uuid"})),
    LeadCore(respond(body={**_ADMITTED, "lead_id": None})),
    LeadCore(respond(body={k: v for k, v in _ADMITTED.items() if k != "lead_id"})),
    LeadCore(respond(body={**_ADMITTED, "score": "high"})),
    LeadCore(respond(body={"outcome": "REJECTED", "errors": []})),
    LeadCore(respond(body={"outcome": "REJECTED"})),
    LeadCore(respond(body={"outcome": "REJECTED", "errors": [{"field": "email"}]})),
    LeadCore(respond(body=[_ADMITTED])),
], ids=["unreachable", "timeout", "500", "503", "422", "token-endpoint-down", "malformed-json", "unknown-outcome",
        "no-outcome", "lead-id-not-uuid", "lead-id-null", "lead-id-missing", "score-not-int",
        "rejected-without-errors", "rejected-without-errors-key", "error-without-message", "body-not-an-object"])
def test_anything_but_a_complete_decision_is_unavailable(lead_core):
    with pytest.raises(AdmissionUnavailable):
        _admit(lead_core)


def test_a_refused_token_is_dropped_so_the_next_call_fetches_another():
    lead_core = LeadCore(respond(401, {"error": True, "error_code": "UNAUTHORIZED"}))
    client, _ = client_for(lead_core)
    adapter = HttpLeadAdmission(client)

    for _ in range(2):
        with pytest.raises(AdmissionUnavailable):
            adapter.admit(_admission_request())

    assert len(lead_core.token_requests) == 2


def test_the_call_carries_the_callers_request_id_and_none_outside_a_request():
    lead_core = LeadCore(respond(body=_ADMITTED))
    reset = request_id_var.set("req-123")
    try:
        _admit(lead_core)
    finally:
        request_id_var.reset(reset)
    _admit(lead_core)

    inside, outside = lead_core.calls
    assert inside.headers["X-Request-Id"] == "req-123"
    assert "X-Request-Id" not in outside.headers
    assert lead_core.token_requests[0].headers["X-Request-Id"] == "req-123"


def test_the_failure_never_carries_the_secret_or_the_token():
    lead_core = LeadCore(respond(500, {"detail": "boom"}))

    with pytest.raises(AdmissionUnavailable) as caught:
        _admit(lead_core)

    assert "secret" not in str(caught.value) and TOKEN["access_token"] not in str(caught.value)
