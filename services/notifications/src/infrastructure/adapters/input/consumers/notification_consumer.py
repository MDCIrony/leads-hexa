from collections.abc import Callable

from chassis.consumer import Envelope

from application.ports.input.notifications import NotificationHandlerInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.notifications.notification_handler import NotificationHandler


class NotificationConsumer:
    """Handles one envelope of a notification consumer group, at most once.

    The processed mark and the notices share one transaction: a failure undoes
    both, so a redelivery retries the whole thing, and a duplicate finds the
    mark and does nothing."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort], group: str) -> None:
        self._uow_factory = uow_factory
        self._group = group
        self._handler: NotificationHandlerInputPort = NotificationHandler()

    def __call__(self, envelope: Envelope) -> None:
        with self._uow_factory() as uow:
            if uow.processed_events.mark(self._group, envelope.event_id):
                self._handler.apply(envelope.event_type, envelope.tenant_id, envelope.payload, uow)
