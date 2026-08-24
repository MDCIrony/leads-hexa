import logging
from typing import Callable, Sequence

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
        """One pass. Returns how many entries went out."""
        delivered = 0
        with self.uow_factory() as uow:
            for entry in uow.outbox.list_unpublished(batch_size):
                error = None
                # A dispatcher that fails must not stop the others from
                # trying to deliver the same entry — same rule as
                # InMemoryEventPublisher with its handlers. An entry counts
                # as delivered only once every dispatcher has it, so a
                # partial failure is retried in full on the next pass.
                for dispatcher in self.dispatchers:
                    try:
                        dispatcher.dispatch(entry)
                    except Exception as exc:
                        error = str(exc)
                        _LOGGER.error(
                            "Dispatcher %s failed for outbox entry %s",
                            dispatcher, entry.id, exc_info=True,
                        )
                if error is None:
                    uow.outbox.mark_published(entry.id)
                    delivered += 1
                else:
                    uow.outbox.mark_failed(entry.id, error)
        return delivered
