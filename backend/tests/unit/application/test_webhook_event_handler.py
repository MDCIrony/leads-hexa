import uuid
from unittest.mock import Mock
from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus, WebhookEventType
from domain.entities.webhook import WebhookConfig
from application.handlers.webhook_event_handler import WebhookEventHandler


def test_webhook_event_handler_dispatches_correctly() -> None:
    mock_webhook_repo = Mock()
    mock_webhook_dispatcher = Mock()

    handler = WebhookEventHandler(
        webhook_repo=mock_webhook_repo,
        webhook_dispatcher=mock_webhook_dispatcher,
    )

    tenant_id_str = str(uuid.uuid4())

    config = WebhookConfig.create(
        tenant_id=tenant_id_str,
        event_type=WebhookEventType.LEAD_PROCESSED,
        target_url="https://hooks.example.com/lead",
        secret_token="secret_abc",
    )
    mock_webhook_repo.get_by_tenant_and_event.return_value = [config]

    event = LeadProcessedEvent(
        tenant_id=tenant_id_str,
        lead_id="lead-123",
        email="test@example.com",
        score=75,
        status=LeadStatus.QUALIFIED,
    )

    handler.handle_lead_processed(event)

    mock_webhook_repo.get_by_tenant_and_event.assert_called_once_with(
        tenant_id=tenant_id_str,
        event_type=WebhookEventType.LEAD_PROCESSED,
    )
    mock_webhook_dispatcher.dispatch.assert_called_once_with(
        target_url="https://hooks.example.com/lead",
        secret_token="secret_abc",
        payload={
            "lead_id": "lead-123",
            "email": "test@example.com",
            "score": 75,
            "status": "QUALIFIED",
        },
    )
