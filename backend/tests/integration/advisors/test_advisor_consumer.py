import json
from uuid import UUID

from chassis.consumer import Envelope
from chassis.testing.contracts import load_fixture

from infrastructure.adapters.input.consumers.advisor_consumer import AdvisorConsumer
from infrastructure.adapters.input.consumers.groups import ADVISORS_GROUP, CONSUMER_GROUPS, DLQ_TOPIC_SPECS
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork


def _envelope(**payload_changes) -> Envelope:
    body = load_fixture("events/AgentState.v1.json")
    body["payload"].update(payload_changes)
    if "tenant_id" in payload_changes:
        body["tenant_id"] = payload_changes["tenant_id"]
    return Envelope.from_bytes(json.dumps(body).encode())


def _stored(test_db, envelope: Envelope):
    with PostgresUnitOfWork(test_db) as uow:
        return uow.advisors.get(UUID(envelope.payload["agent_id"]), UUID(envelope.payload["tenant_id"]))


def test_the_contract_fixture_lands_as_an_advisor(test_db):
    consumer, envelope = AdvisorConsumer(lambda: PostgresUnitOfWork(test_db)), _envelope()

    consumer(envelope)

    advisor = _stored(test_db, envelope)
    assert (advisor.name, advisor.role.value, advisor.is_active, advisor.version, advisor.group_id) == (
        "Ana Pérez", "AGENT", True, 3, None)


def test_a_redelivered_older_state_changes_nothing(test_db):
    consumer = AdvisorConsumer(lambda: PostgresUnitOfWork(test_db))
    consumer(_envelope())

    consumer(_envelope(is_active=False, version=2))

    assert _stored(test_db, _envelope()).is_active is True


def test_the_platform_admin_state_is_ignored(test_db):
    AdvisorConsumer(lambda: PostgresUnitOfWork(test_db))(_envelope(tenant_id=None, role="ADMIN"))

    with test_db.get_connection(autocommit=True) as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM advisors").fetchone()["count"] == 0


def test_the_group_reads_identity_agents_and_declares_its_own_dead_letter_topic():
    assert CONSUMER_GROUPS == {ADVISORS_GROUP: "internal.identity.agents"}
    assert [(spec.name, spec.partitions, spec.config) for spec in DLQ_TOPIC_SPECS] == [
        ("internal.dlq.lead-core.advisors", 1, {"cleanup.policy": "delete", "retention.ms": "604800000"})]
