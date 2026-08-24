from application.handlers.notification_handler import NotificationHandler
from domain.events.notification_events import (
    IntakeRejected,
    LeadAssigned,
    LeadLeftUnassigned,
    LeadReassigned,
)
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.di.container import Container


def subscribe_notification_handlers(container: Container) -> None:
    """Wired the same way in the API and in the worker.

    Whichever process runs the use case is the one publishing its events, and
    since ADR-0027 that is usually not the API. A subscription registered in
    only one of them is a notification the user simply never receives — with
    nothing failing anywhere to say so."""
    handler = NotificationHandler(uow_factory=lambda: PostgresUnitOfWork(container.database))
    for event_type, callback in (
        (LeadAssigned, handler.handle_lead_assigned),
        (LeadReassigned, handler.handle_lead_reassigned),
        (LeadLeftUnassigned, handler.handle_lead_left_unassigned),
        (IntakeRejected, handler.handle_intake_rejected),
    ):
        container.event_publisher.subscribe(event_type, callback)
