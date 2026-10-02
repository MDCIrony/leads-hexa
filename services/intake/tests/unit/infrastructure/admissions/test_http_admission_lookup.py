import httpx
import pytest
from chassis.testing.contracts import assert_conforms, load_fixture
from uuid import UUID, uuid4

from application.ports.output.admissions import AdmissionUnavailable
from infrastructure.adapters.output.admissions.http_admission_lookup import HttpAdmissionLookup
from tests.unit.infrastructure.admissions.lead_core_double import LeadCore, client_for, respond

_LOOKUP = load_fixture("lead-core/admission-lookup.v1.json")


def _lookup(lead_core: LeadCore, ids: list[UUID]):
    client, _ = client_for(lead_core)
    return HttpAdmissionLookup(client).lookup(ids)


def _ids_of(request: httpx.Request) -> list[str]:
    return request.url.params.get_list("intake_record_ids")


def test_the_fixture_conforms_to_the_schema():
    assert_conforms(_LOOKUP, "schemas/lead-core/admission-lookup.v1.schema.json")


def test_the_ids_travel_as_a_repeated_parameter_and_the_items_come_back():
    lead_core = LeadCore(respond(body=_LOOKUP))
    ids = [uuid4(), uuid4()]

    items = _lookup(lead_core, ids)

    [call] = lead_core.calls
    assert (call.method, call.url.path) == ("GET", "/internal/v1/admissions")
    assert _ids_of(call) == [str(i) for i in ids]
    [item] = items
    expected = _LOOKUP["items"][0]
    assert (item.intake_record_id, item.tenant_id, item.lead_id) == (
        expected["intake_record_id"], expected["tenant_id"], expected["lead_id"])


def test_more_than_200_ids_go_in_batches_and_the_answers_are_joined():
    lead_core = LeadCore(respond(body=_LOOKUP))

    items = _lookup(lead_core, [uuid4() for _ in range(450)])

    assert [len(_ids_of(c)) for c in lead_core.calls] == [200, 200, 50]
    assert len(items) == 3


def test_no_ids_means_no_call():
    lead_core = LeadCore(respond(body=_LOOKUP))

    assert _lookup(lead_core, []) == []
    assert lead_core.calls == []


@pytest.mark.parametrize("lead_core", [
    LeadCore(fail=httpx.ConnectError("refused")),
    LeadCore(respond(500, {"error": True})),
    LeadCore(respond(422, {"error": True})),
    LeadCore(respond(content=b"not json")),
    LeadCore(respond(body={"items": [{"intake_record_id": "x"}]})),
    LeadCore(respond(body={})),
], ids=["unreachable", "500", "422", "malformed-json", "malformed-item", "no-items"])
def test_anything_but_a_valid_answer_is_unavailable(lead_core):
    with pytest.raises(AdmissionUnavailable):
        _lookup(lead_core, [uuid4()])
