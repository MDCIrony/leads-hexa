import logging
import threading
from typing import Optional

from application.services.outbox_relay import OutboxRelay

_LOGGER = logging.getLogger(__name__)


class OutboxRelayThread:
    """Ticks OutboxRelay.drain() on an interval, in a daemon thread.

    A thread and not FastAPI's BackgroundTasks (ADR-0025): those are
    per-request, and this work is periodic and owns no request of its own."""

    def __init__(self, relay: OutboxRelay, interval_seconds: float = 1.0) -> None:
        self._relay = relay
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            # Bounded: a pass mid-flush against an unresponsive broker can take
            # minutes, and shutdown must not wait behind it. The thread is a
            # daemon, so what it leaves unfinished dies with the process, and
            # the next start picks those entries back up — they are still
            # unpublished rows.
            self._thread.join(timeout=self._interval_seconds + 5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._relay.drain()
            except Exception:
                # One bad pass (a dropped connection, a transient DB error)
                # must not kill the loop that would otherwise recover on
                # the next tick.
                _LOGGER.error("Outbox relay pass failed", exc_info=True)
            self._stop_event.wait(self._interval_seconds)
