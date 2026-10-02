"""In-memory unit of work and outbox. No database, no I/O."""
from dataclasses import dataclass
from typing import Any

from application.ports.output.outbox import OutboxRepositoryPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.events.internal_event import InternalEvent
from tests.unit.application.doubles.auth_repositories import (
    InMemoryAgentMfaRepository,
    InMemoryAuthChallengeRepository,
    InMemoryAuthSessionRepository,
    InMemorySocialIdentityRepository,
)
from tests.unit.application.doubles.repositories import InMemoryAgentRepository, InMemoryTenantRepository


@dataclass(frozen=True)
class RecordedEvent:
    event_type: str
    partition_key: str
    channel: str
    payload: dict[str, Any]


class InMemoryOutboxRepository(OutboxRepositoryPort):
    def __init__(self) -> None:
        self.entries: list[RecordedEvent] = []

    def record(self, event: InternalEvent, channel: str = "internal") -> None:
        self.entries.append(RecordedEvent(event.event_type, event.partition_key, channel, event.as_payload()))


class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(self) -> None:
        self.agents = InMemoryAgentRepository()
        self.tenants = InMemoryTenantRepository()
        self.sessions = InMemoryAuthSessionRepository()
        self.challenges = InMemoryAuthChallengeRepository()
        self.mfa = InMemoryAgentMfaRepository()
        self.social_identities = InMemorySocialIdentityRepository()
        self.outbox = InMemoryOutboxRepository()
        self._outbox_snapshot: list[RecordedEvent] = []

    def __enter__(self) -> "InMemoryUnitOfWork":
        # Only the outbox honours rollback: it is the write whose survival a test
        # must tell apart from the transaction it belongs to.
        self._outbox_snapshot = list(self.outbox.entries)
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        self.outbox.entries = self._outbox_snapshot

    def events(self, event_type: str | None = None) -> list[RecordedEvent]:
        return [e for e in self.outbox.entries if event_type is None or e.event_type == event_type]
