import json
from pathlib import Path

import pytest

from chassis.consumer.envelope import Envelope
from chassis.testing.contracts import assert_conforms, contracts_root, load_fixture

REPO_CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
EVENT_FIXTURES = sorted(p.name for p in (REPO_CONTRACTS / "fixtures" / "events").glob("*.v1.json"))


def test_contracts_root_finds_the_repository_directory():
    assert contracts_root() == REPO_CONTRACTS


def test_contracts_root_also_searches_from_the_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert contracts_root() == REPO_CONTRACTS


def test_every_internal_event_has_a_fixture():
    assert EVENT_FIXTURES == sorted(f"{name}.v1.json" for name in (
        "AgentState", "TenantState", "LeadAssigned", "LeadReassigned", "LeadLeftUnassigned", "IntakeRejected"))


@pytest.mark.parametrize("name", EVENT_FIXTURES)
def test_event_fixture_conforms_to_its_schema_and_parses_as_an_envelope(name):
    envelope = load_fixture(f"events/{name}")
    event_type = name.removesuffix(".v1.json")
    assert envelope["event_type"] == event_type
    assert_conforms(envelope, f"events/{event_type}.v1.schema.json")
    assert_conforms(envelope, "events/envelope.v1.schema.json")
    assert Envelope.from_bytes(json.dumps(envelope).encode()).event_type == event_type


@pytest.mark.parametrize("fixture,schema", [("identity/agent.v1.json", "schemas/identity/agent.v1.schema.json"),
                                            ("identity/service-token.v1.json",
                                             "schemas/identity/service-token.v1.schema.json")])
def test_identity_fixtures_conform(fixture, schema):
    assert_conforms(load_fixture(fixture), schema)


def test_an_envelope_without_event_id_does_not_conform():
    envelope = load_fixture("events/LeadAssigned.v1.json")
    del envelope["event_id"]
    with pytest.raises(AssertionError, match="event_id"):
        assert_conforms(envelope, "events/LeadAssigned.v1.schema.json")


@pytest.mark.parametrize("field,value", [("event_type", "LeadReassigned"), ("tenant_id", None),
                                         ("schema_version", True), ("occurred_at", "2026-10-02 09:15")])
def test_an_envelope_that_breaks_its_event_schema_does_not_conform(field, value):
    envelope = load_fixture("events/LeadAssigned.v1.json") | {field: value}
    with pytest.raises(AssertionError):
        assert_conforms(envelope, "events/LeadAssigned.v1.schema.json")


def test_a_payload_missing_a_field_does_not_conform():
    envelope = load_fixture("events/AgentState.v1.json")
    del envelope["payload"]["version"]
    with pytest.raises(AssertionError, match="version"):
        assert_conforms(envelope, "events/AgentState.v1.schema.json")


def test_the_platform_admin_agent_state_has_no_tenant():
    envelope = load_fixture("events/AgentState.v1.json")
    envelope["tenant_id"] = envelope["payload"]["tenant_id"] = None
    envelope["payload"]["role"] = "ADMIN"
    assert_conforms(envelope, "events/AgentState.v1.schema.json")


def test_an_unknown_payload_field_is_a_compatible_change():
    envelope = load_fixture("events/TenantState.v1.json")
    envelope["payload"]["plan"] = "pro"
    assert_conforms(envelope, "events/TenantState.v1.schema.json")


def test_contracts_module_does_not_import_jsonschema_eagerly():
    source = (Path(__file__).resolve().parents[1] / "src/chassis/testing/contracts.py").read_text()
    top_level = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert not any("jsonschema" in line or "referencing" in line for line in top_level)
