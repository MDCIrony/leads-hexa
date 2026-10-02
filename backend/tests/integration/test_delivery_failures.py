"""What the delivery chain promises when a hop fails: a duplicate creates no second
effect, a poison event is parked instead of blocking, a failing job is retried
by the broker and bounded by its delivery limit. Real database, doubles for the brokers."""
import json
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from chassis.consumer import ConsumerLoop, Envelope, dlq_topic
from chassis.outbox import OutboxRelay, envelope

from application.dtos.commands import ReceiveIntakeCommand
from application.handlers.notification_handler import NotificationHandler
from application.use_cases.receive_intake_use_case import ReceiveIntakeUseCase
from domain.entities.agent import Agent
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant
from domain.events.notification_events import LeadAssigned
from domain.services.assignment_engine import AssignmentEngine
from domain.value_objects.enums import (
    AgentRole, IntakeJobStatus, IntakeRecordStatus, LeadSourceKind,
)
from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.queue.intake_queue_topology import (
    DLQ_NAME, QUEUE_NAME, declare_intake_topology,
)
from infrastructure.workers import job_messages
from infrastructure.workers.job_messages import process_job_message

_GROUP = "notifications.lead-events"
_TOPIC = "internal.lead-core.events"


def _count(test_db, sql: str, params: tuple = ()) -> int:
    with test_db.get_connection(autocommit=True) as conn:
        return conn.execute(sql, params).fetchone()["n"]


def _seed_assigned_event(test_db) -> LeadAssigned:
    """An agent (notifications reference it) and a LeadAssigned in the internal channel."""
    with PostgresUnitOfWork(test_db) as uow:
        tenant = uow.tenants.save(Tenant.create(name=f"Org {uuid4()}"))
        agent = uow.agents.save(
            Agent.create("Ana", f"{uuid4()}@test.com", role=AgentRole.AGENT, tenant_id=tenant.id.value)
        )
        event = LeadAssigned(
            tenant_id=str(tenant.id.value), lead_id=str(uuid4()), agent_id=str(agent.id.value),
        )
        uow.outbox.record(event, channel="internal")
    return event


class _CapturingDispatcher:
    def __init__(self) -> None:
        self.delivered = []

    def dispatch(self, row) -> None:
        self.delivered.append(row)


class _MarkDiesStore:
    """The real store, except that recording the outcome fails: the relay
    delivered and then died before it could say so."""

    def __init__(self, store) -> None:
        self._store = store

    def fetch(self, channel, limit):
        return self._store.fetch(channel, limit)

    def mark_published(self, row_id):
        raise RuntimeError("relay died after delivering")

    def mark_failed(self, row_id, error):
        self._store.mark_failed(row_id, error)


def test_a_row_delivered_twice_after_a_relay_crash_notifies_once(test_db):
    event = _seed_assigned_event(test_db)
    dispatcher = _CapturingDispatcher()

    @contextmanager
    def dying_store():
        with open_outbox_store(test_db) as store:
            yield _MarkDiesStore(store)

    with pytest.raises(RuntimeError, match="relay died"):
        OutboxRelay(dying_store, {"internal": [dispatcher]}).drain("internal")
    # The next pass, on a healthy relay, finds the row unmarked and delivers it again.
    assert OutboxRelay(lambda: open_outbox_store(test_db), {"internal": [dispatcher]}).drain("internal") == 1

    assert [row.id for row in dispatcher.delivered] == [event.event_id, event.event_id]
    consumer = NotificationConsumer(lambda: PostgresUnitOfWork(test_db), _GROUP)
    for row in dispatcher.delivered:
        consumer(Envelope.from_bytes(json.dumps(envelope(row, "lead-core")).encode()))

    assert _count(test_db, "SELECT COUNT(*) AS n FROM notifications WHERE lead_id = %s",
                  (UUID(event.lead_id),)) == 1
    assert _count(test_db, "SELECT COUNT(*) AS n FROM outbox_events WHERE published_at IS NOT NULL") == 1


class _Message:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def value(self): return self._value
    def key(self): return b"lead"
    def topic(self): return _TOPIC
    def partition(self): return 1
    def offset(self): return 7
    def headers(self): return [("event_type", b"LeadAssigned")]


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


def test_an_event_whose_effect_always_fails_is_dead_lettered_and_committed(test_db, monkeypatch):
    event = _seed_assigned_event(test_db)
    with open_outbox_store(test_db) as store:
        (row,) = store.fetch("internal", 10)
    message = _Message(json.dumps(envelope(row, "lead-core")).encode())

    attempts = []

    def _boom(self, *args):
        attempts.append(args)
        raise RuntimeError("effect failed")

    monkeypatch.setattr(NotificationHandler, "apply", _boom)
    consumer, producer = _Consumer(), _Producer()
    loop = ConsumerLoop(
        consumer, producer, _GROUP, [_TOPIC],
        NotificationConsumer(lambda: PostgresUnitOfWork(test_db), _GROUP),
        sleep=lambda _: None,
    )

    assert loop.process(message) == "dead-lettered"

    assert len(attempts) == 3
    (sent,) = producer.produced
    assert sent["topic"] == dlq_topic(_GROUP) == "internal.dlq.notifications.lead-events"
    assert dict(sent["headers"])["attempts"] == b"3"
    assert sent["value"] == message.value()
    # Committed, so the partition moves on instead of replaying the poison message.
    assert consumer.commits == [{"message": message, "asynchronous": False}]
    assert _count(test_db, "SELECT COUNT(*) AS n FROM notifications") == 0
    assert _count(test_db, "SELECT COUNT(*) AS n FROM processed_events WHERE event_id = %s",
                  (event.event_id,)) == 0


class _Container:
    def __init__(self, test_db) -> None:
        self._db = test_db
        self.assignment_engine = AssignmentEngine()
        self.file_parser = None

    def unit_of_work(self):
        return PostgresUnitOfWork(self._db)


class _FailingIngest:
    def execute(self, command, existing_record=None):
        raise RuntimeError("scoring blew up")


def test_a_job_with_a_failing_record_is_nacked_and_stays_unfinished(test_db, monkeypatch):
    payload = {"first_name": "Maria", "last_name": "Gomez", "company": "TechCorp",
               "budget": 5000, "industry": "Tech", "email": "mgomez@techcorp.com"}
    with PostgresUnitOfWork(test_db) as uow:
        tenant = uow.tenants.save(Tenant.create(name=f"Org {uuid4()}"))
        tenant_id = tenant.id.value
        uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Form", kind=LeadSourceKind.MANUAL_FORM))
        uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))
    received = ReceiveIntakeUseCase(uow=PostgresUnitOfWork(test_db)).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind="SINGLE", payloads=[payload], filename=None, content=None)
    )
    message = {"tenant_id": str(tenant_id), "job_id": received.job_id, "correlation_id": None}
    monkeypatch.setattr(job_messages, "get_ingest_lead_use_case", lambda uow, container: _FailingIngest())

    assert process_job_message(_Container(test_db), message) == "nack"

    with PostgresUnitOfWork(test_db) as uow:
        [record] = uow.intake_records.list_by_tenant(tenant_id, job_id=UUID(received.job_id))
        job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    assert record.status == IntakeRecordStatus.PENDING
    assert job.status != IntakeJobStatus.COMPLETED


class _Channel:
    def __init__(self) -> None:
        self.queues = {}

    def queue_declare(self, queue, durable=False, arguments=None):
        self.queues[queue] = {"durable": durable, "arguments": arguments or {}}


def test_the_queue_still_dead_letters_after_three_deliveries():
    channel = _Channel()

    declare_intake_topology(channel)

    assert channel.queues[DLQ_NAME]["durable"] is True
    assert channel.queues[QUEUE_NAME]["arguments"] == {
        "x-queue-type": "quorum",
        "x-delivery-limit": 3,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": DLQ_NAME,
    }
