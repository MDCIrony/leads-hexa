from types import SimpleNamespace

import pytest

from infrastructure.workers import intake_worker


class _Channel:
    def __init__(self):
        self.calls = []

    def basic_nack(self, delivery_tag, requeue):
        self.calls.append(("nack", delivery_tag, requeue))

    def basic_ack(self, delivery_tag):
        self.calls.append(("ack", delivery_tag))


@pytest.mark.parametrize("body", [b"[]", b'{"tenant_id": 1, "job_id": 2}', b"{}", b"not json"])
def test_a_malformed_body_is_dead_lettered_instead_of_killing_the_worker(body):
    channel = _Channel()

    intake_worker._handle_message(None, channel, SimpleNamespace(delivery_tag=7), body)

    assert channel.calls == [("nack", 7, False)]
