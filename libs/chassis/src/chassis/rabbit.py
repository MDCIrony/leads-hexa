"""RabbitMQ job dispatcher with publisher confirms."""
import json
import logging
from typing import Any, Callable, Optional

import pika
from pika.exceptions import NackError, UnroutableError

from chassis.outbox import OutboxRow

_LOGGER = logging.getLogger(__name__)


class _Rejected(RuntimeError):
    """The broker refused the message: neither a reconnect nor a retry will help."""


class RabbitJobDispatcher:
    """Publishes one outbox row to a queue with publisher confirms: dispatch()
    returns only once the broker confirmed, so published_at never precedes it.

    Holds one lazily opened connection, so it belongs to the single relay thread:
    pika's BlockingConnection is not safe to share across threads."""

    def __init__(
        self,
        url: str,
        queue: str,
        declare: Callable[[Any], None],
        message: Callable[[OutboxRow], dict],
        timeout_seconds: float = 5.0,
        connection_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._url = url
        self._queue = queue
        self._declare = declare
        self._message = message
        self._timeout_seconds = timeout_seconds
        self._connect = connection_factory or self._open_connection
        self._connection = None
        self._channel = None

    def _open_connection(self):
        parameters = pika.URLParameters(self._url)
        # Bounded on purpose: pika's defaults (three attempts, ten seconds each)
        # would stall the relay for half a minute on an unreachable broker.
        parameters.connection_attempts = 1
        parameters.socket_timeout = self._timeout_seconds
        return pika.BlockingConnection(parameters)

    def _is_open(self) -> bool:
        return (self._connection is not None and not self._connection.is_closed
                and self._channel is not None and not self._channel.is_closed)

    def _channel_ready(self):
        if self._is_open():
            return self._channel
        self._reset()
        connection = self._connect()
        try:
            channel = connection.channel()
            channel.confirm_delivery()
            # Declared on every new connection: the queue may have been lost with a
            # broker restart, and declaring is a no-op when it already matches.
            self._declare(channel)
        except Exception:
            self._close(connection)
            raise
        self._connection, self._channel = connection, channel
        return channel

    def dispatch(self, row: OutboxRow) -> None:
        reused = self._is_open()
        try:
            self._publish(row)
        except _Rejected:
            raise
        except Exception:
            self._reset()
            if not reused:
                raise
            # An idle connection dies silently (heartbeats are only serviced during
            # I/O) while is_closed stays False; retry once on a fresh one so a
            # stale socket does not cost the row an attempt.
            _LOGGER.info("Reused RabbitMQ connection failed, retrying on a fresh one", exc_info=True)
            try:
                self._publish(row)
            except _Rejected:
                raise
            except Exception:
                self._reset()
                raise

    def _publish(self, row: OutboxRow) -> None:
        try:
            self._channel_ready().basic_publish(
                exchange="",
                routing_key=self._queue,
                body=json.dumps(self._message(row)).encode(),
                properties=pika.BasicProperties(
                    delivery_mode=2, message_id=str(row.id), content_type="application/json",
                ),
                mandatory=True,
            )
        except (NackError, UnroutableError) as exc:
            # The broker answered, so the connection is fine; the row is not.
            raise _Rejected(f"RabbitMQ did not accept row {row.id} for {self._queue}: {exc!r}") from exc

    def _reset(self) -> None:
        connection, self._connection, self._channel = self._connection, None, None
        if connection is not None:
            self._close(connection)

    @staticmethod
    def _close(connection) -> None:
        try:
            connection.close()
        except Exception:
            _LOGGER.debug("Closing a broken RabbitMQ connection failed", exc_info=True)
