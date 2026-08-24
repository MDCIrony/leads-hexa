from application.dtos.commands import OutboxEntry
from application.ports.output.outbound_dispatcher_port import OutboundDispatcherPort
from application.ports.output.webhook_dispatcher_port import WebhookDispatcherPort
from application.ports.output.webhook_repository_port import WebhookRepositoryPort
from domain.value_objects.enums import WebhookEventType

# Only LeadProcessedEvent has a webhook audience today (ADR-0023): a client
# already receiving processed-lead webhooks must not start getting the
# disqualified ones too just because they now flow through the same outbox.
# Anything else recorded in the outbox (LeadDisqualified today, more later)
# simply has no configs to match and dispatch() is a no-op for it.
_WEBHOOK_EVENT_TYPES = {"LeadProcessedEvent": WebhookEventType.LEAD_PROCESSED}


class WebhookOutboundDispatcher(OutboundDispatcherPort):
    """Wraps the webhook subsystem so the relay can deliver to it.

    The lookup and HTTP delivery are exactly what WebhookEventHandler
    already does; only the outbox entry's generic shape is new, so this
    adapts that shape onto the same two ports instead of duplicating them."""

    def __init__(
        self,
        webhook_repo: WebhookRepositoryPort,
        webhook_dispatcher: WebhookDispatcherPort,
    ) -> None:
        self.webhook_repo = webhook_repo
        self.webhook_dispatcher = webhook_dispatcher

    def dispatch(self, entry: OutboxEntry) -> None:
        event_type = _WEBHOOK_EVENT_TYPES.get(entry.event_type)
        if event_type is None:
            return
        configs = self.webhook_repo.get_by_tenant_and_event(
            tenant_id=entry.tenant_id, event_type=event_type
        )
        for config in configs:
            delivered = self.webhook_dispatcher.dispatch(
                target_url=config.target_url,
                secret_token=config.secret_token,
                payload=entry.payload,
            )
            if not delivered:
                raise RuntimeError(f"Webhook delivery to {config.target_url} failed")
