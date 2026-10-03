import uuid
import pytest
from domain.leads.lead import Lead
from domain.rules.scoring_rule import ScoringRule
from domain.webhooks.webhook import WebhookConfig
from domain.exceptions import InvalidEmailException
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    LeadStatus,
    Operator,
    WebhookEventType,
)
from domain.value_objects.criterion import Criterion

def test_lead_entity_lifecycle():
    lead = Lead.create(
        tenant_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000,
        industry="Technology",
        custom_attributes={"employee_count": 150},
    )

    assert lead.status == LeadStatus.NEW
    assert int(lead.score) == 0

    lead.apply_score(45)
    assert int(lead.score) == 45

    lead.qualify()
    assert lead.status == LeadStatus.QUALIFIED

    agent_id = AgentId()
    lead.assign_to(agent_id, lead.tenant_id)
    assert lead.status == LeadStatus.ASSIGNED
    assert lead.assigned_agent_id == agent_id

def test_qualify_moves_a_low_score_lead_to_qualified_not_new():
    """Acceptance criterion 5: qualify() has no threshold of its own anymore,
    so nothing leaves a processed lead stuck in NEW."""
    lead = Lead.create(
        tenant_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        first_name="Bajo",
        last_name="Puntaje",
        company="TechCorp",
        budget=100,
        industry="tech",
    )
    lead.apply_score(5)

    lead.qualify()

    assert lead.status == LeadStatus.QUALIFIED

def test_scoring_rule_entity_creation():
    rule = ScoringRule.create(
        tenant_id=uuid.uuid4(),
        name="High Budget",
        conditions=[Criterion.create(field="budget", operator="GREATER_THAN", value=10000)],
        score_delta=25,
        rule_id=str(uuid.uuid4()),
    )
    assert rule.score_delta == 25
    assert rule.conditions[0].operator == Operator.GREATER_THAN
    assert isinstance(rule.id, uuid.UUID)

def test_webhook_config_entity_creation():
    tenant_uuid = uuid.uuid4()
    webhook = WebhookConfig.create(
        tenant_id=str(tenant_uuid),
        event_type="LEAD_INGESTED",
        target_url="https://example.com/webhook",
        secret_token="secret123",
    )
    assert isinstance(webhook.tenant_id, TenantId)
    assert webhook.tenant_id.value == tenant_uuid
    assert webhook.event_type == WebhookEventType.LEAD_INGESTED
    assert webhook.target_url == "https://example.com/webhook"
    assert webhook.secret_token == "secret123"
    assert isinstance(webhook.id, uuid.UUID)


class TestLeadLifecycleFields:
    def test_the_new_statuses_exist(self):
        assert LeadStatus.UNASSIGNED.value == "UNASSIGNED"
        assert LeadStatus.DISCARDED.value == "DISCARDED"

    def test_a_fresh_lead_carries_no_assignment_trace(self):
        lead = Lead.create(
            tenant_id=uuid.uuid4(), source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
            email="ana@x.test", company="C", budget=100, industry="tech",
        )
        assert lead.assigned_at is None
        assert lead.discard_reason is None
        assert lead.updated_at is not None


class TestLeadOptionalEmail:
    def _base_kwargs(self):
        return dict(
            tenant_id=uuid.uuid4(), source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
            company="C", budget=100, industry="tech",
        )

    def test_a_lead_can_be_created_without_an_email(self):
        lead = Lead.create(**self._base_kwargs(), email=None)
        assert lead.email is None

    def test_an_empty_email_string_is_treated_as_absent(self):
        lead = Lead.create(**self._base_kwargs(), email="")
        assert lead.email is None

    def test_a_malformed_email_still_raises(self):
        with pytest.raises(InvalidEmailException):
            Lead.create(**self._base_kwargs(), email="no-es-correo")
