import json
import uuid
from uuid import UUID

import psycopg
import pytest
from chassis.consumer import ConsumerLoop, Envelope
from chassis.testing.contracts import load_fixture

from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.input.consumers.groups import DLQ_TOPIC_SPECS, INTAKE_TENANTS_GROUP, handler_for
from infrastructure.adapters.input.consumers.tenant_consumer import TenantConsumer
from infrastructure.adapters.output.persistence.lead_source_repository import PostgresLeadSourceRepository
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


def _envelope(event_id: str = None, **payload_changes) -> Envelope:
    body = load_fixture("events/TenantState.v1.json")
    body["payload"].update(payload_changes)
    if event_id is not None:
        body["event_id"] = event_id
    return Envelope.from_bytes(json.dumps(body).encode())


def _consumer(test_db) -> TenantConsumer:
    return TenantConsumer(lambda: PostgresUnitOfWork(test_db), INTAKE_TENANTS_GROUP)


def _tenant_id(envelope: Envelope) -> UUID:
    return UUID(envelope.payload["tenant_id"])


def _sources(test_db, tenant_id: UUID) -> list:
    with PostgresUnitOfWork(test_db) as uow:
        return sorted((s.name, s.kind.value, s.field_mapping, s.is_active) for s in uow.sources.list_by_tenant(tenant_id))


def _count(test_db, sql: str, params: tuple) -> int:
    with test_db.get_connection(autocommit=True) as conn:
        return conn.execute(sql, params).fetchone()["n"]


def test_the_contract_fixture_provisions_the_default_sources_in_one_transaction(test_db):
    envelope = _envelope()

    _consumer(test_db)(envelope)

    assert _sources(test_db, _tenant_id(envelope)) == [
        ("Carga de fichero", "FILE_UPLOAD", {}, True), ("Formulario manual", "MANUAL_FORM", {}, True)]
    assert _count(test_db, "SELECT COUNT(*) AS n FROM provisioned_tenants WHERE tenant_id = %s",
                  (_tenant_id(envelope),)) == 1
    assert _count(test_db, "SELECT COUNT(*) AS n FROM processed_events WHERE consumer = %s AND event_id = %s",
                  (INTAKE_TENANTS_GROUP, envelope.event_id)) == 1


def test_rereading_the_same_state_does_not_duplicate(test_db):
    consumer = _consumer(test_db)
    consumer(_envelope())

    consumer(_envelope())
    consumer(_envelope(event_id=str(uuid.uuid4()), version=2))

    assert len(_sources(test_db, _tenant_id(_envelope()))) == 2


def test_a_provisioned_tenant_does_not_get_a_deleted_source_back(test_db):
    consumer, envelope = _consumer(test_db), _envelope()
    consumer(envelope)
    with PostgresUnitOfWork(test_db) as uow:
        source = uow.sources.get_by_kind(_tenant_id(envelope), LeadSourceKind.FILE_UPLOAD)
        uow.sources.delete(source.id.value, _tenant_id(envelope))

    consumer(_envelope(event_id=str(uuid.uuid4()), version=2))

    assert _sources(test_db, _tenant_id(envelope)) == [("Formulario manual", "MANUAL_FORM", {}, True)]


def test_a_tenant_with_monolith_sources_is_marked_without_duplicates(test_db):
    envelope = _envelope()
    with PostgresUnitOfWork(test_db) as uow:
        uow.sources.save(LeadSource.create(tenant_id=_tenant_id(envelope), name="Formulario manual",
                                           kind=LeadSourceKind.MANUAL_FORM))

    _consumer(test_db)(envelope)

    assert _sources(test_db, _tenant_id(envelope)) == [("Formulario manual", "MANUAL_FORM", {}, True)]
    assert _count(test_db, "SELECT COUNT(*) AS n FROM provisioned_tenants WHERE tenant_id = %s",
                  (_tenant_id(envelope),)) == 1


def test_an_inactive_state_marks_without_creating(test_db):
    consumer, envelope = _consumer(test_db), _envelope(is_active=False)

    consumer(envelope)
    consumer(_envelope(event_id=str(uuid.uuid4()), version=2))

    assert _sources(test_db, _tenant_id(envelope)) == []


def test_other_event_types_are_ignored(test_db):
    body = load_fixture("events/TenantState.v1.json")
    body["event_type"] = "SomethingElse"

    _consumer(test_db)(Envelope.from_bytes(json.dumps(body).encode()))

    assert _count(test_db, "SELECT COUNT(*) AS n FROM processed_events", ()) == 0


def test_the_worker_routes_the_group_to_this_consumer_and_declares_its_dead_letters(test_db):
    assert isinstance(handler_for(INTAKE_TENANTS_GROUP, lambda: PostgresUnitOfWork(test_db)), TenantConsumer)
    assert [spec.name for spec in DLQ_TOPIC_SPECS] == ["internal.dlq.intake.tenants"]


class _Message:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def value(self): return self._value
    def key(self): return b"tenant"
    def topic(self): return "internal.identity.tenants"
    def partition(self): return 0
    def offset(self): return 3
    def headers(self): return []


class _Consumer:
    def __init__(self) -> None:
        self.commits = []

    def commit(self, **kwargs):
        self.commits.append(kwargs)


class _Producer:
    def __init__(self) -> None:
        self.produced = []

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](None, None)

    def flush(self, timeout):
        return 0


def _written(test_db) -> int:
    return _count(test_db, "SELECT (SELECT COUNT(*) FROM lead_sources) + (SELECT COUNT(*) FROM provisioned_tenants)"
                           " + (SELECT COUNT(*) FROM processed_events) AS n", ())


@pytest.mark.parametrize("changes", [
    {"tenant_id": None}, {"tenant_id": "not-a-uuid"}, {"is_active": None}, {"is_active": "true"},
])
def test_a_malformed_state_is_dead_lettered_without_writing_anything(test_db, changes):
    body = load_fixture("events/TenantState.v1.json")
    body["payload"].update(changes)
    message, consumer, producer = _Message(json.dumps(body).encode()), _Consumer(), _Producer()
    # Same retryable as the worker lane: only a database outage is waited out.
    loop = ConsumerLoop(consumer, producer, INTAKE_TENANTS_GROUP, ["internal.identity.tenants"],
                        _consumer(test_db), sleep=lambda _: None,
                        retryable=lambda exc: isinstance(exc, psycopg.OperationalError))

    assert loop.process(message) == "dead-lettered"

    (sent,) = producer.produced
    assert sent["topic"] == "internal.dlq.intake.tenants"
    assert consumer.commits == [{"message": message, "asynchronous": False}]
    assert _written(test_db) == 0


def test_a_state_without_tenant_id_writes_nothing(test_db):
    body = load_fixture("events/TenantState.v1.json")
    del body["payload"]["tenant_id"]

    with pytest.raises(ValueError):
        _consumer(test_db)(Envelope.from_bytes(json.dumps(body).encode()))

    assert _written(test_db) == 0


def test_a_failure_after_the_first_source_undoes_both_marks_and_the_source(test_db, monkeypatch):
    original_save, saves = PostgresLeadSourceRepository.save, []

    def fail_on_second(self, source):
        saves.append(source)
        if len(saves) == 2:
            raise RuntimeError("second source failed")
        return original_save(self, source)

    monkeypatch.setattr(PostgresLeadSourceRepository, "save", fail_on_second)
    envelope = _envelope()
    with pytest.raises(RuntimeError):
        _consumer(test_db)(envelope)
    assert _written(test_db) == 0

    monkeypatch.setattr(PostgresLeadSourceRepository, "save", original_save)
    _consumer(test_db)(envelope)

    assert len(_sources(test_db, _tenant_id(envelope))) == 2
