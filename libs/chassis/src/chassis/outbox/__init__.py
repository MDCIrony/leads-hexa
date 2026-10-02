"""Transactional-outbox delivery shared by every service that publishes events.

No broker library is imported here: producers are injected, so the relay and the
dispatchers are testable and the package loads in services that use only one transport."""
from chassis.outbox.envelope import envelope
from chassis.outbox.kafka import KafkaEventDispatcher
from chassis.outbox.relay import Dispatcher, OutboxRelay, OutboxStore, run_relay
from chassis.outbox.row import OutboxRow

__all__ = ["Dispatcher", "KafkaEventDispatcher", "OutboxRelay", "OutboxRow", "OutboxStore", "envelope", "run_relay"]
