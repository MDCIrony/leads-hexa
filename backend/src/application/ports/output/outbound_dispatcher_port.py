from abc import ABC, abstractmethod

from application.dtos.commands import OutboxEntry


class OutboundDispatcherPort(ABC):
    """One transport the relay can deliver an outbox entry to.

    Must raise to signal failure rather than swallow it: that is the only
    way OutboxRelay knows an entry needs to stay unpublished for retry."""

    @abstractmethod
    def dispatch(self, entry: OutboxEntry) -> None: ...
