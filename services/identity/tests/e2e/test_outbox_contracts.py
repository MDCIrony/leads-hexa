"""Every write the API makes records its state in the outbox, and the row the relay
will publish conforms to the event contracts other services consume."""
from chassis.outbox import OutboxRow
from chassis.outbox.envelope import envelope
from chassis.testing.contracts import assert_conforms

from tests.e2e.seeds import bootstrap_admin, create_agent, create_organization

_SCHEMAS = {"AgentState": "events/AgentState.v1.schema.json", "TenantState": "events/TenantState.v1.schema.json"}


def _envelopes(client) -> list[dict]:
    with client.app.state.container.database.get_connection(autocommit=True) as conn:
        rows = conn.execute(
            "SELECT id, channel, tenant_id, partition_key, event_type, payload, occurred_on, correlation_id"
            " FROM outbox_events ORDER BY occurred_on, id"
        ).fetchall()
    return [
        envelope(OutboxRow(**{**row, "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None}), "identity")
        for row in rows
    ]


def test_every_api_write_records_a_conforming_state_event(client):
    admin = bootstrap_admin(client)
    tenant, manager = create_organization(client, admin)
    agent_id = create_agent(client, manager).json()["id"]
    client.patch(f"/api/v1/agents/{agent_id}", json={"name": "Renamed"}, headers=manager)
    client.delete(f"/api/v1/agents/{agent_id}", headers=manager)
    client.patch(f"/api/v1/tenants/{tenant['id']}", json={"is_active": False}, headers=admin)

    envelopes = _envelopes(client)

    for event in envelopes:
        assert_conforms(event, _SCHEMAS[event["event_type"]])
    assert [e["event_type"] for e in envelopes] == [
        "AgentState",                   # bootstrap admin
        "TenantState", "AgentState",    # organization and its manager, one transaction
        "AgentState", "AgentState", "AgentState",  # agent created, renamed, deactivated
        "AgentState", "TenantState",    # suspension deactivates the manager, then the tenant
    ]
    assert envelopes[0]["tenant_id"] is None
    agent_versions = [e["payload"]["version"] for e in envelopes if e["aggregate_id"] == agent_id]
    assert agent_versions == sorted(agent_versions) and len(set(agent_versions)) == 3
    assert {e["producer"] for e in envelopes} == {"identity"}


def test_the_request_id_travels_as_the_correlation_id(client):
    client.post(
        "/api/v1/agents", json={"name": "Root", "email": "root@plat.test", "password": "Secret123"},
        headers={"X-Request-ID": "req-identity-1"},
    )

    assert [e["correlation_id"] for e in _envelopes(client)] == ["req-identity-1"]
