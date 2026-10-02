import logging
import threading
import time
from typing import Callable

from chassis.consumer.loop import ConsumerLoop

_LOGGER = logging.getLogger(__name__)


def run_consumer_lane(
    name: str, build_loop: Callable[[], ConsumerLoop],
    ready: threading.Event, stop: threading.Event,
    max_backoff_seconds: float = 30.0,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Builds a consumer and runs it; on any failure builds a new one after a capped backoff.

    A fatal Kafka error or a failed subscribe ends one consumer, not the lane:
    nothing restarts a dead thread, and under the dev file watcher a crashed
    process stays up doing nothing. Only `stop` ends this."""
    # `ready` means this service's own topics are declared: its DLQs and, in a
    # process that also produces, its outbound topics. Input topics belong to
    # their producer; a consumer never auto-creates them (librdkafka defaults
    # allow.auto.create.topics to false), it waits for them to appear.
    while not ready.wait(0.5):
        if stop.is_set():
            return
    delay = 1.0
    while not stop.is_set():
        started = clock()
        try:
            build_loop().run(stop)
        except Exception as exc:
            _LOGGER.warning("Consumer lane %s failed (%s), retrying in %.0fs", name, exc, delay)
            _LOGGER.debug("Consumer lane %s failed", name, exc_info=True)
            # A consumer that ran for a while before failing is a new incident,
            # not a continuation of the last one.
            if clock() - started > max_backoff_seconds:
                delay = 1.0
            if stop.wait(delay):
                return
            delay = min(delay * 2, max_backoff_seconds)
