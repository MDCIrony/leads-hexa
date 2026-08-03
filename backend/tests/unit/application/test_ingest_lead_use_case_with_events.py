import uuid
from unittest.mock import Mock
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.dtos.commands import IngestLeadCommand
from domain.events.lead_events import LeadProcessedEvent


def test_ingest_lead_publishes_event() -> None:
    mock_lead_repo = Mock()
    mock_rule_repo = Mock()
    mock_agent_repo = Mock()
    mock_event_publisher = Mock()

    mock_rule_repo.get_scoring_rules_by_tenant.return_value = []
    mock_rule_repo.get_routing_rules_by_tenant.return_value = []

    mock_lead_repo.save.side_effect = lambda l: l

    use_case = IngestLeadUseCase(
        lead_repo=mock_lead_repo,
        rule_repo=mock_rule_repo,
        agent_repo=mock_agent_repo,
        event_publisher=mock_event_publisher,
    )

    tenant_id_val = uuid.uuid4()

    command = IngestLeadCommand(
        tenant_id=tenant_id_val,
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone=None,
        company="Acme Corp",
        budget=5000.0,
        industry="Tech",
        custom_attributes={},
    )

    result = use_case.execute(command)

    assert result.error is None
    assert mock_event_publisher.publish.call_count == 1
    event_arg = mock_event_publisher.publish.call_args[0][0]
    assert isinstance(event_arg, LeadProcessedEvent)
    assert event_arg.tenant_id == str(tenant_id_val)
