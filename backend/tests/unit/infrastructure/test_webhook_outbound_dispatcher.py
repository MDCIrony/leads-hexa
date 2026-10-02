import uuid
from unittest.mock import Mock

from chassis.outbox import OutboxRow

from domain.entities.lead import Lead
from domain.entities.webhook import WebhookConfig
from domain.events.lead_events import LeadDisqualified, LeadProcessedEvent
from domain.value_objects.enums import LeadStatus, WebhookEventType
from domain.value_objects.score_breakdown import AppliedRule
from infrastructure.adapters.output.events.webhook_outbound_dispatcher import (
    WebhookOutboundDispatcher,
)

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


def _entry_of(event) -> OutboxRow:
    """Exactly what the relay reads back out of the outbox."""
    return OutboxRow(
        id=event.event_id,
        channel="product",
        tenant_id=event.tenant_id,
        partition_key=event.partition_key,
        event_type=event.event_type,
        payload=event.as_payload(),
        occurred_on=event.occurred_on,
        correlation_id=None,
    )


def _dispatcher(delivered: bool = True):
    repo, sender = Mock(), Mock()
    sender.dispatch.return_value = delivered
    repo.get_by_tenant_and_event.return_value = [
        WebhookConfig.create(
            tenant_id=str(_TENANT),
            event_type=WebhookEventType.LEAD_PROCESSED,
            target_url="https://hooks.example.com/lead",
            secret_token="secret_abc",
        )
    ]
    return WebhookOutboundDispatcher(webhook_repo=repo, webhook_dispatcher=sender), repo, sender


def test_the_customer_receives_the_whole_contract():
    lead = _qualified_lead()
    event = LeadProcessedEvent.of(lead)
    dispatcher, repo, sender = _dispatcher()

    dispatcher.dispatch(_entry_of(event))

    repo.get_by_tenant_and_event.assert_called_once_with(
        tenant_id=str(_TENANT), event_type=WebhookEventType.LEAD_PROCESSED
    )
    sender.dispatch.assert_called_once_with(
        target_url="https://hooks.example.com/lead",
        secret_token="secret_abc",
        payload={
            # Its deduplication key: the receiver gets this entry again if a
            # relay pass dies between delivering it and marking it published.
            "event_id": str(event.event_id),
            "occurred_on": event.occurred_on.isoformat(),
            "schema_version": 1,
            "tenant_id": str(_TENANT),
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


def test_a_disqualified_lead_is_not_sent_to_the_webhook():
    """A client already receiving processed-lead webhooks must not start
    getting the filtered ones too just because both share an outbox now
    (ADR-0023)."""
    dispatcher, repo, sender = _dispatcher()
    event = LeadDisqualified(
        tenant_id=str(_TENANT), lead_id=str(uuid.uuid4()),
        source_id=str(_SOURCE), reason="Sin forma de contactar",
    )

    dispatcher.dispatch(_entry_of(event))

    repo.get_by_tenant_and_event.assert_not_called()
    sender.dispatch.assert_not_called()


def test_a_failed_delivery_raises_so_the_relay_can_retry():
    """The relay marks an entry published when dispatch returns without
    raising. A silent False would mark a webhook nobody received as sent."""
    lead = _qualified_lead()
    dispatcher, _, _ = _dispatcher(delivered=False)

    try:
        dispatcher.dispatch(_entry_of(LeadProcessedEvent.of(lead)))
    except RuntimeError:
        return
    raise AssertionError("dispatch must raise when the webhook was not delivered")
