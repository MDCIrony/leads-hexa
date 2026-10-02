import json
import uuid
from uuid import UUID

from chassis.consumer import Envelope
from chassis.testing.contracts import load_fixture

from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.input.consumers.groups import INTAKE_TENANTS_GROUP, handler_for
from infrastructure.adapters.input.consumers.intake.tenant_consumer import TenantConsumer
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork


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

    # The tenant is not in leads_db's tenants table: after the cut it is born in identity.
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


def test_the_worker_routes_the_group_to_this_consumer(test_db):
    assert isinstance(handler_for(INTAKE_TENANTS_GROUP, lambda: PostgresUnitOfWork(test_db)), TenantConsumer)
