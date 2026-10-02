"""The `intake.jobs` consumer against a scripted pika connection: no broker, no sleeps."""
import json
import queue
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pika.exceptions import AMQPError, ConnectionWrongStateError

from infrastructure.worker import job_consumer
from infrastructure.worker.job_consumer import JobRunner, consume
from infrastructure.worker.rabbit_lane import run_job_consumer

_BODY = json.dumps({"tenant_id": str(uuid4()), "job_id": str(uuid4()), "correlation_id": "req-1"}).encode()


class _Channel:
    def __init__(self) -> None:
        self.settled, self.callback, self.cancelled, self.prefetch = [], None, [], None

    def queue_declare(self, queue, durable, arguments=None): ...

    def basic_qos(self, prefetch_count):
        self.prefetch = prefetch_count

    def basic_consume(self, queue, on_message_callback):
        self.callback = on_message_callback
        return "ctag"

    def basic_cancel(self, consumer_tag):
        self.cancelled.append(consumer_tag)

    def basic_ack(self, delivery_tag):
        self.settled.append(("ack", delivery_tag, threading.current_thread().name))

    def basic_nack(self, delivery_tag, requeue):
        self.settled.append(("nack", delivery_tag, requeue, threading.current_thread().name))


class _Connection:
    """Like pika: thread-safe callbacks run only inside process_data_events, on the caller's thread.

    Delivers `body` on the first pump; sets `stop` after `stop_after_pumps` pumps."""

    def __init__(self, body: bytes, stop: threading.Event, stop_after_pumps: int | None = None) -> None:
        self._channel, self._body, self._stop = _Channel(), body, stop
        self._stop_after = stop_after_pumps
        self._callbacks: queue.Queue = queue.Queue()
        self.pumps, self.scheduled_from = 0, []

    def channel(self):
        return self._channel

    def add_callback_threadsafe(self, callback):
        self.scheduled_from.append(threading.current_thread().name)
        self._callbacks.put(callback)

    def process_data_events(self, time_limit):
        self.pumps += 1
        assert self.pumps < 10_000, "the consumer never settled"
        if self.pumps == 1:
            self._channel.callback(self._channel, SimpleNamespace(delivery_tag=7), None, self._body)
        try:
            self._callbacks.get(timeout=0.01)()
        except queue.Empty:
            pass
        if self._stop_after is not None and self.pumps >= self._stop_after:
            self._stop.set()


def _long_job(connection: _Connection, pumps_needed: int):
    """A job that only finishes once the main thread has pumped `pumps_needed` times while it ran:
    the stand-in for a job longer than the heartbeat."""
    seen = {}

    def process(message):
        assert threading.current_thread() is not threading.main_thread()
        start, idle = connection.pumps, threading.Event()
        while connection.pumps - start < pumps_needed:
            idle.wait(0.005)
        seen["pumped_during_job"] = connection.pumps - start
        seen["thread"] = threading.current_thread().name
        return "ack"

    return process, seen


def test_a_long_job_runs_off_the_connection_thread_which_keeps_pumping_and_settles_the_ack():
    stop = threading.Event()
    connection = _Connection(_BODY, stop, stop_after_pumps=40)
    process, seen = _long_job(connection, pumps_needed=20)

    consume(connection, process, stop)

    assert seen["pumped_during_job"] >= 20 and seen["thread"] == "intake-job"
    # Scheduled from the job thread, executed by the thread that pumps the connection.
    assert connection.scheduled_from == ["intake-job"]
    assert connection._channel.settled == [("ack", 7, threading.current_thread().name)]
    assert connection._channel.prefetch == 1


def test_a_stop_during_a_job_takes_no_new_one_but_lets_the_running_one_settle():
    stop = threading.Event()
    connection = _Connection(_BODY, stop, stop_after_pumps=2)
    process, _ = _long_job(connection, pumps_needed=10)

    consume(connection, process, stop)

    assert connection._channel.cancelled == ["ctag"]
    assert [s[0] for s in connection._channel.settled] == ["ack"]


@pytest.mark.parametrize("body", [b"[]", b'{"tenant_id": 1, "job_id": 2}', b"{}", b"not json"])
def test_a_malformed_body_is_dead_lettered_without_starting_a_job(body):
    channel, calls = _Channel(), []
    runner = JobRunner(_Connection(body, threading.Event()), calls.append, lambda _: False)

    runner.on_message(channel, SimpleNamespace(delivery_tag=7), None, body)

    assert [s[:3] for s in channel.settled] == [("nack", 7, False)]
    assert calls == [] and not runner.busy()


def _settle_one(outcome: str):
    log, channel = [], _Channel()
    connection = _Connection(_BODY, threading.Event())
    original = connection.add_callback_threadsafe
    connection.add_callback_threadsafe = lambda cb: (log.append("scheduled"), original(cb))
    runner = JobRunner(connection, lambda message: outcome, lambda delay: log.append(("waited", delay)) or False)

    runner.on_message(channel, SimpleNamespace(delivery_tag=7), None, _BODY)
    runner.join()
    connection._callbacks.get_nowait()()
    return log, channel.settled


def test_an_interrupted_job_is_requeued_only_after_the_delay():
    log, settled = _settle_one("nack")

    assert log == [("waited", job_consumer._REQUEUE_DELAY_SECONDS), "scheduled"]
    assert job_consumer._REQUEUE_DELAY_SECONDS == 10
    assert [s[:3] for s in settled] == [("nack", 7, True)]


def test_a_finished_job_is_acked_without_waiting():
    log, settled = _settle_one("ack")

    assert log == ["scheduled"]
    assert [s[:2] for s in settled] == [("ack", 7)]


def test_a_job_that_raises_is_still_settled_as_a_requeue():
    def explode(message):
        raise RuntimeError("boom")

    channel, connection = _Channel(), _Connection(_BODY, threading.Event())
    runner = JobRunner(connection, explode, lambda _: False)
    runner.on_message(channel, SimpleNamespace(delivery_tag=7), None, _BODY)
    runner.join()
    connection._callbacks.get_nowait()()

    assert [s[:3] for s in channel.settled] == [("nack", 7, True)] and not runner.busy()


def test_a_connection_lost_before_settling_is_logged_not_raised(caplog):
    connection = _Connection(_BODY, threading.Event())

    def lost(callback):
        raise ConnectionWrongStateError("closed")

    connection.add_callback_threadsafe = lost
    runner = JobRunner(connection, lambda message: "ack", lambda _: False)
    runner.on_message(_Channel(), SimpleNamespace(delivery_tag=7), None, _BODY)
    runner.join()

    assert "Connection lost before settling" in caplog.text


class _Stop:
    def __init__(self) -> None:
        self.waits, self._set = [], False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, delay):
        self.waits.append(delay)
        return self._set


def test_the_lane_reconnects_with_backoff_on_any_amqp_error_and_on_os_errors():
    stop, failures = _Stop(), [AMQPError("channel closed"), OSError("name does not resolve"), AMQPError("lost")]

    def connect(url):
        error = failures.pop(0)
        if not failures:
            stop.set()
        raise error

    run_job_consumer("amqp://broker", lambda m: "ack", stop, connect=connect, clock=lambda: 0.0)

    assert stop.waits == [1.0, 2.0, 4.0]
