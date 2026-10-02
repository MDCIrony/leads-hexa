from typing import Callable

from chassis.outbox import Dispatcher, OutboxRelay


def build_dispatchers(job: Dispatcher) -> dict[str, list[Dispatcher]]:
    """Dispatchers by outbox channel.

    `internal` starts empty and is filled once its topics exist: the relay skips
    a channel with no dispatcher, so rows wait instead of reaching a topic that
    Kafka would auto-create without the intended configuration."""
    return {"internal": [], "job": [job]}


def build_relays(store: Callable, dispatchers: dict[str, list[Dispatcher]]) -> dict[str, OutboxRelay]:
    """One relay per channel, each on its own thread.

    Delivery is sequential inside a relay, so a shared one would let an
    unreachable Kafka on `internal` hold the jobs up behind it. Each gets the
    channel's own list, which keeps the late activation of `internal` visible
    to its relay."""
    return {channel: OutboxRelay(store, {channel: lanes}) for channel, lanes in dispatchers.items()}
