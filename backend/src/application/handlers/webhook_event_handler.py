from application.ports.output.webhook_repository_port import WebhookRepositoryPort
from application.ports.output.webhook_dispatcher_port import WebhookDispatcherPort
from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import WebhookEventType


class WebhookEventHandler:
    """Event handler that dynamically dispatches webhooks upon LeadProcessedEvent."""

    def __init__(
        self,
        webhook_repo: WebhookRepositoryPort,
        webhook_dispatcher: WebhookDispatcherPort,
    ) -> None:
        self.webhook_repo = webhook_repo
        self.webhook_dispatcher = webhook_dispatcher

    def handle_lead_processed(self, event: LeadProcessedEvent) -> None:
        """Fetch matching active webhooks for tenant and event type, then dispatch."""
        configs = self.webhook_repo.get_by_tenant_and_event(
            tenant_id=event.tenant_id,
            event_type=WebhookEventType.LEAD_PROCESSED,
        )

        # The whole contract, not an identifier: the receiver is outside this
        # system and has no API call to make to find out who the lead is.
        payload = {
            "lead_id": event.lead_id,
            "source_id": event.source_id,
            "first_name": event.first_name,
            "last_name": event.last_name,
            "email": event.email,
            "phone": event.phone,
            "company": event.company,
            "industry": event.industry,
            "budget": event.budget,
            "custom_attributes": event.custom_attributes,
            "score": event.score,
            "score_breakdown": event.score_breakdown,
            "status": event.status.value,
            "assigned_agent_id": event.assigned_agent_id,
            "assigned_at": event.assigned_at,
            "created_at": event.created_at,
        }

        for config in configs:
            self.webhook_dispatcher.dispatch(
                target_url=config.target_url,
                secret_token=config.secret_token,
                payload=payload,
            )
