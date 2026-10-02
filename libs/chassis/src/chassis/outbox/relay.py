import logging
import threading
from contextlib import contextmanager
from typing import Callable, ContextManager, Mapping, Optional, Protocol, Sequence
from uuid import UUID

from chassis.outbox.envelope import OutboxRow
from chassis.web import request_id_var

_LOGGER = logging.getLogger(__name__)


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
