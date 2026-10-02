"""Transactional-outbox delivery shared by every service that publishes events.

No broker library is imported here: producers are injected, so the relay and the
dispatchers are testable and the module loads in services that use only one transport."""
import json
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, ContextManager, Mapping, Optional, Protocol, Sequence
from uuid import UUID

from chassis.web import request_id_var

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboxRow:
    id: UUID
    channel: str
    tenant_id: Optional[str]
    partition_key: str
    event_type: str
    payload: dict
    occurred_on: datetime
    correlation_id: Optional[str]


class OutboxStore(Protocol):
    def fetch(self, channel: str, limit: int) -> list[OutboxRow]: ...
    def mark_published(self, row_id: UUID) -> None: ...
    def mark_failed(self, row_id: UUID, error: str) -> None: ...


class Dispatcher(Protocol):
    def dispatch(self, row: OutboxRow) -> None:
        """Raises on failure."""


@contextmanager
def _correlated(correlation_id: Optional[str]):
    """Tags the relay's own log lines with the id of the request that wrote the row."""
    token = request_id_var.set(correlation_id) if correlation_id else None
    try:
        yield
    finally:
        if token is not None:
            request_id_var.reset(token)


class OutboxRelay:
    """Delivers what the outbox holds, channel by channel, and marks what got through.

    A channel is an independent delivery lane (product webhooks, internal events,
    jobs): its dispatchers, its backlog and its failures never touch another's."""

    def __init__(
        self,
        store: Callable[[], ContextManager[OutboxStore]],
        dispatchers: Mapping[str, Sequence[Dispatcher]],
    ) -> None:
        self._store = store
        self._dispatchers = dispatchers

    def drain(self, channel: str, batch_size: int = 100) -> int:
        """One pass over one channel. Returns how many rows went out.

        Three steps and not one, because the middle one talks to the network:
        read, deliver, record. Delivering inside the reading transaction
        would hold a pooled connection — and the rows it selected — open for
        as long as the slowest receiver takes to answer, and a handful of
        timing-out webhooks would drain the pool the API needs to serve."""
        dispatchers = self._dispatchers.get(channel)
        # Without a dispatcher nothing could deliver the rows, and marking them
        # failed would burn attempts on a channel that is merely not wired yet.
        if not dispatchers:
            return 0

        with self._store() as store:
            rows = store.fetch(channel, batch_size)

        outcomes = []
        for row in rows:
            # One traceback per pass is enough to diagnose an outage; a full
            # one for every queued row would bury everything else in the log.
            traced = any(error is not None for _, error in outcomes)
            outcomes.append((row, self._deliver(row, dispatchers, traced)))

        with self._store() as store:
            for row, error in outcomes:
                if error is None:
                    store.mark_published(row.id)
                else:
                    store.mark_failed(row.id, error)
        return sum(1 for _, error in outcomes if error is None)

    def drain_all(self, batch_size: int = 100) -> dict[str, int]:
        counts = {}
        for channel in self._dispatchers:
            try:
                counts[channel] = self.drain(channel, batch_size)
            except Exception:
                # A broken channel must not starve the others of their pass.
                _LOGGER.error("Draining outbox channel %s failed", channel, exc_info=True)
                counts[channel] = 0
        return counts

    @staticmethod
    def _deliver(row: OutboxRow, dispatchers: Sequence[Dispatcher], traced: bool = False) -> Optional[str]:
        """Hands the row to every dispatcher of its channel. Returns the last error, if any.

        A dispatcher that fails must not stop the others from trying. The row
        counts as delivered only once every dispatcher has it, so a partial
        failure is retried in full, and a consumer that sees it twice
        deduplicates by event id."""
        error = None
        with _correlated(row.correlation_id):
            for dispatcher in dispatchers:
                try:
                    dispatcher.dispatch(row)
                except Exception as exc:
                    if traced or error is not None:
                        _LOGGER.warning("Dispatcher %s failed for outbox row %s: %s", dispatcher, row.id, exc)
                    else:
                        _LOGGER.error(
                            "Dispatcher %s failed for outbox row %s", dispatcher, row.id, exc_info=True,
                        )
                    error = str(exc)
        return error


def run_relay(relay: OutboxRelay, stop: threading.Event, interval_seconds: float = 1.0) -> None:
    """Loops drain_all until stop is set; one failed pass is logged, never fatal."""
    while not stop.is_set():
        try:
            relay.drain_all()
        except Exception:
            # A database restart or a broker blip must not end the thread that
            # nothing else restarts; the next pass retries the same rows.
            _LOGGER.error("Outbox relay pass failed", exc_info=True)
        stop.wait(interval_seconds)


def envelope(row: OutboxRow, producer: str, schema_version: int = 1) -> dict:
    return {
        "event_id": str(row.id),
        "event_type": row.event_type,
        "schema_version": schema_version,
        "occurred_at": row.occurred_on.isoformat(),
        "producer": producer,
        "tenant_id": row.tenant_id,
        "aggregate_id": row.partition_key,
        "correlation_id": row.correlation_id,
        "payload": row.payload,
    }


class KafkaEventDispatcher:
    """Internal events: envelope as value, partition_key as key, event_type and
    correlation_id as headers. Delivery confirmed through the callback + flush,
    same as the product dispatcher today.

    The producer must be created with `acks=all` and `enable.idempotence=true`
    (no loss on a leader change, no duplicates from internal retries), and with
    `message.timeout.ms` close to `flush_timeout_seconds`, so a message the
    producer is still retrying is not delivered after the row was marked failed."""

    def __init__(
        self,
        producer,
        producer_name: str,
        topic_for: Callable[[OutboxRow], str],
        flush_timeout_seconds: float = 10.0,
    ) -> None:
        self._producer = producer
        self._producer_name = producer_name
        self._topic_for = topic_for
        self._flush_timeout_seconds = flush_timeout_seconds

    def dispatch(self, row: OutboxRow) -> None:
        topic = self._topic_for(row)
        delivery_error = None

        def _on_delivery(err, _msg):
            nonlocal delivery_error
            if err is not None:
                delivery_error = err

        headers = [("event_type", row.event_type.encode())]
        if row.correlation_id:
            headers.append(("correlation_id", row.correlation_id.encode()))
        self._producer.produce(
            topic=topic,
            key=row.partition_key.encode(),
            value=json.dumps(envelope(row, self._producer_name)).encode(),
            headers=headers,
            on_delivery=_on_delivery,
        )
        # flush(), not poll(): the relay marks the row published the moment
        # dispatch() returns without raising. flush()'s return value alone
        # cannot tell success from a completed-with-error delivery, so
        # failure is read from the delivery callback it drives instead.
        pending = self._producer.flush(self._flush_timeout_seconds)
        if pending > 0:
            raise RuntimeError(f"Kafka flush timed out with {pending} message(s) undelivered")
        if delivery_error is not None:
            raise RuntimeError(f"Kafka delivery failed for topic {topic}: {delivery_error}")
