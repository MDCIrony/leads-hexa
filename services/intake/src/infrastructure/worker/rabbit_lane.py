import logging
import threading
import time
from typing import Callable

import pika
from pika.exceptions import AMQPError

from infrastructure.worker.job_consumer import Process, consume

_LOGGER = logging.getLogger(__name__)
_MAX_BACKOFF_SECONDS = 30.0
# Explicit rather than whatever the broker proposes: the job thread keeps the
# connection's thread free to answer it, so a job may run far longer than this.
_HEARTBEAT_SECONDS = 30


def connect(url: str):
    parameters = pika.URLParameters(url)
    parameters.heartbeat = _HEARTBEAT_SECONDS
    return pika.BlockingConnection(parameters)


def run_job_consumer(
    url: str, process: Process, stop: threading.Event,
    connect: Callable[[str], object] = connect, clock: Callable[[], float] = time.monotonic,
) -> None:
    """Consumes `intake.jobs`, reconnecting with a capped backoff, until `stop` is set.

    Reconnects in process instead of exiting: under the dev file watcher an
    exited worker stays down until a file changes, and the jobs the relay
    keeps publishing would wait for nobody."""
    delay = 1.0
    while not stop.is_set():
        started = clock()
        try:
            connection = connect(url)
            try:
                consume(connection, process, stop)
            finally:
                if connection.is_open:
                    connection.close()
        # AMQPError in general: a lost stream, a closed channel or a wrong-state
        # connection all mean the same here. OSError too: a broker host that does
        # not resolve surfaces as socket.gaierror, which pika re-raises unwrapped.
        except (AMQPError, OSError) as exc:
            if clock() - started > _MAX_BACKOFF_SECONDS:
                delay = 1.0
            _LOGGER.warning("RabbitMQ unavailable (%r), reconnecting in %.0fs", exc, delay)
            stop.wait(delay)
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)
