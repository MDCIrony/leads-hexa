import uuid
from unittest.mock import Mock

from application.handlers.webhook_event_handler import WebhookEventHandler
from domain.entities.lead import Lead
from domain.entities.webhook import WebhookConfig
from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus, WebhookEventType
from domain.value_objects.score_breakdown import AppliedRule

_TENANT = uuid.uuid4()
_SOURCE = uuid.uuid4()
_RULE = uuid.uuid4()


def _qualified_lead() -> Lead:
    return Lead.create(
        tenant_id=_TENANT,
        source_id=_SOURCE,
        first_name="Jane",
        last_name="Doe",
        email="test@example.com",
        phone="+34600000000",
        company="Acme Corp",
        budget="15000.50",
        industry="Tech",
        custom_attributes={"utm_source": "linkedin"},
        score=75,
        score_breakdown=[AppliedRule(rule_id=_RULE, name="Presupuesto alto", score_delta=75)],
        status=LeadStatus.QUALIFIED,
    )


def test_webhook_event_handler_dispatches_correctly() -> None:
    mock_webhook_repo = Mock()
    mock_webhook_dispatcher = Mock()

    handler = WebhookEventHandler(
        webhook_repo=mock_webhook_repo,
        webhook_dispatcher=mock_webhook_dispatcher,
    )

    lead = _qualified_lead()
    config = WebhookConfig.create(
        tenant_id=str(_TENANT),
        event_type=WebhookEventType.LEAD_PROCESSED,
        target_url="https://hooks.example.com/lead",
        secret_token="secret_abc",
    )
    mock_webhook_repo.get_by_tenant_and_event.return_value = [config]

    handler.handle_lead_processed(LeadProcessedEvent.of(lead))

    mock_webhook_repo.get_by_tenant_and_event.assert_called_once_with(
        tenant_id=str(_TENANT),
        event_type=WebhookEventType.LEAD_PROCESSED,
    )
    mock_webhook_dispatcher.dispatch.assert_called_once_with(
        target_url="https://hooks.example.com/lead",
        secret_token="secret_abc",
        payload={
            "lead_id": str(lead.id),
            "source_id": str(_SOURCE),
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "test@example.com",
            "phone": "+34600000000",
            "company": "Acme Corp",
            "industry": "Tech",
            # A string with two decimals, never a float: the budget is money.
            "budget": "15000.50",
            "custom_attributes": {"utm_source": "linkedin"},
            "score": 75,
            "score_breakdown": [
                {"rule_id": str(_RULE), "name": "Presupuesto alto", "score_delta": 75}
            ],
            "status": "QUALIFIED",
            "assigned_agent_id": None,
            "assigned_at": None,
            "created_at": lead.created_at.isoformat(),
        },
    )


def test_the_contract_does_not_alias_the_lead_attributes() -> None:
    """A handler that edits what it received would be editing the lead the
    publisher still holds."""
    lead = _qualified_lead()

    event = LeadProcessedEvent.of(lead)
    event.custom_attributes["utm_source"] = "tampered"

    assert lead.custom_attributes["utm_source"] == "linkedin"
