import json
from uuid import uuid4

GROUP = "notifications.lead-events"


def body(**overrides):
    values = {"event_id": str(uuid4()), "event_type": "LeadAssigned", "schema_version": 1,
              "occurred_at": "2026-01-02T03:04:05+00:00", "producer": "lead-core",
              "tenant_id": "t-1", "aggregate_id": "lead-9", "correlation_id": "corr-1",
              "payload": {"lead_id": "lead-9"}}
    values.update(overrides)
    return values


def raw(**overrides):
    return json.dumps(body(**overrides)).encode()


class FakeMessage:
    def __init__(self, value, key=b"lead-9", topic="internal.lead-core.events",
                 partition=2, offset=41, error=None,
                 headers=(("event_type", b"LeadAssigned"), ("correlation_id", b"corr-1"))):
        self._value, self._key, self._topic = value, key, topic
        self._partition, self._offset = partition, offset
        self._error, self._headers = error, list(headers)

    def value(self): return self._value
    def key(self): return self._key
    def topic(self): return self._topic
    def partition(self): return self._partition
    def offset(self): return self._offset
    def error(self): return self._error
    def headers(self): return self._headers


class FakeConsumer:
    def __init__(self, messages=(), stop=None):
        self.queue, self.stop = list(messages), stop
        self.commits, self.seeks, self.subscribed, self.closed = [], [], None, False
        self.callbacks = {}

    def subscribe(self, topics, **callbacks):
        self.subscribed, self.callbacks = topics, callbacks

    def commit(self, **kwargs): self.commits.append(kwargs)
    def seek(self, partition): self.seeks.append(partition)
    def close(self): self.closed = True

    def poll(self, timeout):
        if self.queue:
            return self.queue.pop(0)
        self.stop.set()
        return None


class FakeProducer:
    def __init__(self, delivery_error=None, pending=0):
        self.delivery_error, self.pending, self.produced = delivery_error, pending, []
        self.flushes, self.closed = [], False

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](self.delivery_error, None)

    def flush(self, timeout):
        self.flushes.append(timeout)
        return self.pending

    def close(self): self.closed = True
