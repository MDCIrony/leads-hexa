import logging
import threading
from typing import Callable, Sequence

from chassis.consumer import TopicSpec, ensure_topics

_LOGGER = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 30.0


def ensure_topics_until_ready(
    admin,
    specs: Sequence[TopicSpec],
    stop: threading.Event,
    on_ready: Callable[[], None],
) -> bool:
    """Retries with backoff until the topics exist; returns False if stopped first.

    A broker that is down must not take the process with it (ADR-0026): the
    product relay keeps running meanwhile."""
    delay = 1.0
    while not stop.is_set():
        try:
            ensure_topics(admin, specs)
        except Exception as exc:
            _LOGGER.warning("Kafka topics not ready (%s), retrying in %.0fs", exc, delay)
            _LOGGER.debug("Kafka topics not ready", exc_info=True)
            if stop.wait(delay):
                return False
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)
        else:
            _LOGGER.info("Kafka topics ensured: %s", ", ".join(spec.name for spec in specs))
            on_ready()
            return True
    return False
