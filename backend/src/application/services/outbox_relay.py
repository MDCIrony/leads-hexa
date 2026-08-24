import logging
from typing import Callable, Optional, Sequence

from application.dtos.commands import OutboxEntry
from application.ports.output.outbound_dispatcher_port import OutboundDispatcherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort

_LOGGER = logging.getLogger(__name__)


class OutboxRelay:
    """Delivers what the outbox holds, and marks what got through.

    Lives in the application layer because it decides delivery policy;
    the thread that ticks it and the transports it delivers to are
    infrastructure."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWorkPort],
        dispatchers: Sequence[OutboundDispatcherPort],
    ) -> None:
        self.uow_factory = uow_factory
        self.dispatchers = dispatchers

    def drain(self, batch_size: int = 100) -> int:
        """One pass. Returns how many entries went out.

        Three steps and not one, because the middle one talks to the network:
        read, deliver, record. Delivering inside the reading transaction
        would hold a pooled connection — and the rows it selected — open for
        as long as the slowest receiver takes to answer, and a handful of
        timing-out webhooks would drain the pool the API needs to serve."""
        with self.uow_factory() as uow:
            entries = uow.outbox.list_unpublished(batch_size)

        outcomes = [(entry, self._deliver(entry)) for entry in entries]

        with self.uow_factory() as uow:
            for entry, error in outcomes:
                if error is None:
                    uow.outbox.mark_published(entry.id)
                else:
                    uow.outbox.mark_failed(entry.id, error)
        return sum(1 for _, error in outcomes if error is None)

    def _deliver(self, entry: OutboxEntry) -> Optional[str]:
        """Hands the entry to every dispatcher. Returns the last error, if any.

        A dispatcher that fails must not stop the others from trying — same
        rule as InMemoryEventPublisher with its handlers. The entry counts as
        delivered only once every dispatcher has it, so a partial failure is
        retried in full, and a consumer that sees it twice deduplicates by
        event id."""
        error = None
        for dispatcher in self.dispatchers:
            try:
                dispatcher.dispatch(entry)
            except Exception as exc:
                error = str(exc)
                _LOGGER.error(
                    "Dispatcher %s failed for outbox entry %s",
                    dispatcher, entry.id, exc_info=True,
                )
        return error
