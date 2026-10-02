import uuid

from application.services.outbox_relay import OutboxRelay
from domain.events.lead_events import LeadDisqualified
from tests.unit.mocks.in_memory_uow import InMemoryOutboxRepository, InMemoryUnitOfWork


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.calls = []

    def dispatch(self, entry) -> None:
        self.calls.append(entry)


class _FailingDispatcher:
    def dispatch(self, entry) -> None:
        raise RuntimeError("boom")


def _event() -> LeadDisqualified:
    return LeadDisqualified(
        tenant_id=str(uuid.uuid4()),
        lead_id=str(uuid.uuid4()),
        source_id=str(uuid.uuid4()),
        reason="Sin forma de contactar",
    )


def _relay(outbox, dispatchers) -> OutboxRelay:
    return OutboxRelay(uow_factory=lambda: InMemoryUnitOfWork(outbox=outbox), dispatchers=dispatchers)


def test_a_failing_dispatcher_does_not_stop_the_others_but_the_entry_stays_undelivered():
    outbox = InMemoryOutboxRepository()
    event = _event()
    outbox.record(event)
    working, failing = _RecordingDispatcher(), _FailingDispatcher()

    delivered = _relay(outbox, [working, failing]).drain()

    # Not counted as delivered: one of the two dispatchers never got it.
    assert delivered == 0
    assert len(working.calls) == 1
    assert working.calls[0].id == event.event_id
    assert event.event_id in outbox.failed_ids
    assert event.event_id not in outbox.published_ids
    # Still there for the next pass — a partial failure must not be lost.
    assert [entry.id for entry in outbox.list_unpublished("product", 10)] == [event.event_id]


def test_a_published_entry_is_not_delivered_again():
    outbox = InMemoryOutboxRepository()
    event = _event()
    outbox.record(event)
    dispatcher = _RecordingDispatcher()
    relay = _relay(outbox, [dispatcher])

    first_pass = relay.drain()
    second_pass = relay.drain()

    assert first_pass == 1
    assert second_pass == 0
    assert len(dispatcher.calls) == 1
    assert outbox.list_unpublished("product", 10) == []


def test_delivery_happens_outside_the_reading_transaction():
    """A dispatcher talks to the network. Doing it inside the transaction
    that read the batch would hold a pooled connection open for as long as
    the slowest receiver takes to answer, and a handful of timing-out
    webhooks would drain the pool the API runs on."""
    outbox = InMemoryOutboxRepository()
    outbox.record(_event())
    open_transactions = []

    class _TransactionCountingUow(InMemoryUnitOfWork):
        def __enter__(self):
            open_transactions.append(1)
            return super().__enter__()

        def __exit__(self, *args):
            open_transactions.pop()
            return super().__exit__(*args)

    class _AssertingDispatcher:
        def dispatch(self, entry) -> None:
            assert not open_transactions, "delivered while a transaction was open"

    relay = OutboxRelay(
        uow_factory=lambda: _TransactionCountingUow(outbox=outbox),
        dispatchers=[_AssertingDispatcher()],
    )

    assert relay.drain() == 1
