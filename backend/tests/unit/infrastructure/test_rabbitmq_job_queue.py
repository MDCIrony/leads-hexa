import uuid

import pika
import pytest

from infrastructure.adapters.output.queue.rabbitmq_job_queue import QUEUE_NAME, RabbitMQJobQueue

_TENANT = uuid.uuid4()
_JOB = uuid.uuid4()


class _FakeChannel:
    """Stands in for pika's BlockingChannel: records what it was asked to
    declare and publish, without a network."""

    def __init__(self):
        self.declared = []
        self.published = []

    def queue_declare(self, queue, durable=True, arguments=None):
        self.declared.append({"queue": queue, "durable": durable, "arguments": arguments})

    def basic_publish(self, exchange, routing_key, body, properties):
        self.published.append(
            {"exchange": exchange, "routing_key": routing_key, "body": body, "properties": properties}
        )


class _FakeConnection:
    def __init__(self, params):
        self.params = params
        self.channel_obj = _FakeChannel()

    def channel(self):
        return self.channel_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_returns_false_and_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    """The endpoint that calls this must be able to fall back instead of
    crashing: a queue outage is not the client's fault."""

    def _refuse_connection(params):
        raise pika.exceptions.AMQPConnectionError("connection refused")

    monkeypatch.setattr(pika, "BlockingConnection", _refuse_connection)
    queue = RabbitMQJobQueue(url="amqp://guest:guest@nowhere:5672/%2F")

    assert queue.enqueue_intake_job(_TENANT, _JOB) is False


def test_publishes_persistently_to_the_intake_jobs_queue_when_it_works(monkeypatch):
    fake_connection = _FakeConnection(None)
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: fake_connection)
    queue = RabbitMQJobQueue(url="amqp://guest:guest@rabbitmq:5672/%2F")

    result = queue.enqueue_intake_job(_TENANT, _JOB)

    assert result is True
    sent = fake_connection.channel_obj.published[0]
    assert sent["routing_key"] == QUEUE_NAME
    assert sent["properties"].delivery_mode == 2
    assert sent["body"] == f'{{"tenant_id": "{_TENANT}", "job_id": "{_JOB}"}}'.encode()


def test_the_message_carries_only_tenant_and_job_id(monkeypatch):
    """The job itself already lives in the database (0.2, 0.3): duplicating
    its payload into the queue would give it two copies that can drift."""
    import json

    fake_connection = _FakeConnection(None)
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: fake_connection)
    queue = RabbitMQJobQueue(url="amqp://guest:guest@rabbitmq:5672/%2F")

    queue.enqueue_intake_job(_TENANT, _JOB)

    payload = json.loads(fake_connection.channel_obj.published[0]["body"])
    assert set(payload.keys()) == {"tenant_id", "job_id"}
