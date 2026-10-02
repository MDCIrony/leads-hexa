import functools
import json
import logging
import threading
from typing import Callable, Literal
from uuid import UUID

from pika.exceptions import AMQPError

from infrastructure.adapters.output.queue.topology import QUEUE_NAME, declare_intake_topology

_LOGGER = logging.getLogger(__name__)

Process = Callable[[dict], Literal["ack", "nack"]]

# A lead-core restart takes seconds; an immediate redelivery would spend the
# job's three deliveries before it is back and dead-letter a job that would
# have succeeded.
_REQUEUE_DELAY_SECONDS = 10.0


def decode(body: bytes) -> dict:
    message = json.loads(body)
    for key in ("tenant_id", "job_id"):
        UUID(message[key])
    return message


class JobRunner:
    """Runs each job on its own thread while the connection's thread keeps pumping events.

    pika services heartbeats only inside process_data_events: a job run inside the
    delivery callback would starve them, and the broker drops a connection that
    stays silent past the heartbeat, taking the job's delivery with it. The
    settlement goes back to the connection's thread through
    add_callback_threadsafe, the only pika call that is safe from another thread."""

    def __init__(self, connection, process: Process, wait: Callable[[float], bool]) -> None:
        self._connection = connection
        self._process = process
        # stop.wait in the worker: a shutdown cuts the requeue delay short.
        self._wait = wait
        self._thread: threading.Thread | None = None
        self._unsettled = 0

    def on_message(self, channel, method, properties, body: bytes) -> None:
        try:
            message = decode(body)
        except Exception as exc:
            # No redelivery fixes a body that is not a job message.
            _LOGGER.warning("Malformed intake job message dead-lettered: %r", exc)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        self._unsettled += 1
        self._thread = threading.Thread(
            target=self._run, args=(channel, method.delivery_tag, message), name="intake-job", daemon=True,
        )
        self._thread.start()

    def busy(self) -> bool:
        return self._unsettled > 0

    def join(self) -> None:
        if self._thread is not None:
            self._thread.join()

    def _run(self, channel, delivery_tag: int, message: dict) -> None:
        try:
            outcome = self._process(message)
        except Exception:
            # Unsettled, the delivery would hold the drain on shutdown forever.
            _LOGGER.error("Intake job %s raised, requeueing", message["job_id"], exc_info=True)
            outcome = "nack"
        if outcome == "ack":
            settle = functools.partial(channel.basic_ack, delivery_tag=delivery_tag)
        else:
            self._wait(_REQUEUE_DELAY_SECONDS)
            settle = functools.partial(channel.basic_nack, delivery_tag=delivery_tag, requeue=True)
        try:
            self._connection.add_callback_threadsafe(functools.partial(self._settle, settle))
        except AMQPError:
            # The connection died under the job: the broker hands the message back
            # on its own, and the next run finds the records this one closed.
            _LOGGER.warning("Connection lost before settling intake job %s", message["job_id"])

    def _settle(self, settle: Callable[[], None]) -> None:
        self._unsettled -= 1
        settle()


def consume(connection, process: Process, stop: threading.Event) -> None:
    """Consumes `intake.jobs` on `connection` until `stop` is set."""
    runner = JobRunner(connection, process, stop.wait)
    try:
        channel = connection.channel()
        declare_intake_topology(channel)
        # One job at a time per worker: jobs are long (up to 10k records), and a
        # deep prefetch would let one worker hoard several while others sit idle.
        channel.basic_qos(prefetch_count=1)
        consumer_tag = channel.basic_consume(queue=QUEUE_NAME, on_message_callback=runner.on_message)
        _LOGGER.info("Intake worker consuming from %s", QUEUE_NAME)
        while not stop.is_set():
            connection.process_data_events(time_limit=1)
        # Take no new job, but let the running one settle: closing now would
        # hand it back to the queue and cost it one of its deliveries.
        channel.basic_cancel(consumer_tag)
        while runner.busy():
            connection.process_data_events(time_limit=1)
    finally:
        # A job still running on a dead connection finishes before the next
        # connection exists, so a redelivery of it never runs side by side with it.
        runner.join()
