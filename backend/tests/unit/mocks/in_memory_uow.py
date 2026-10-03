from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.rules.disqualification_rule_repository_port import (
    DisqualificationRuleRepositoryPort,
)
from application.ports.output.leads.lead_repository_port import LeadRepositoryPort
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from application.ports.output.rules.rule_repository_port import RuleRepositoryPort
from application.ports.output.groups.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import OutboxEntry
from domain.rules.disqualification_rule import DisqualificationRule
from domain.events.internal_event import InternalEvent
from domain.events.lead_events import OutboundEvent
from infrastructure.adapters.output.persistence.correlation import current_correlation_id
from tests.unit.mocks.advisors.in_memory_advisor_repo import InMemoryAdvisorRepository
from tests.unit.mocks.leads.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.rules.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.groups.in_memory_sales_group_repo import InMemorySalesGroupRepository


class InMemoryDisqualificationRuleRepository(DisqualificationRuleRepositoryPort):
    """Kept inline: no other test needs it."""

    def __init__(self) -> None:
        self._rules: Dict[UUID, DisqualificationRule] = {}

    def save(self, rule: DisqualificationRule) -> DisqualificationRule:
        self._rules[rule.id] = rule
        return rule

    def get_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[DisqualificationRule]:
        rule = self._rules.get(rule_id)
        return rule if rule and rule.tenant_id == tenant_id else None

    def list_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[DisqualificationRule]:
        items = [r for r in self._rules.values() if r.tenant_id == tenant_id]
        items.sort(key=lambda r: (-r.priority, str(r.id)))
        return items[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        return sum(1 for r in self._rules.values() if r.tenant_id == tenant_id)

    def delete(self, rule_id: UUID, tenant_id: UUID) -> bool:
        rule = self._rules.get(rule_id)
        if rule and rule.tenant_id == tenant_id:
            del self._rules[rule_id]
            return True
        return False


class InMemoryOutboxRepository(OutboxRepositoryPort):
    """Kept inline (same convention as above)."""

    def __init__(self) -> None:
        self._entries: Dict[UUID, OutboxEntry] = {}
        self.published_ids: List[UUID] = []
        self.failed_ids: List[UUID] = []

    def record(self, event: OutboundEvent | InternalEvent, channel: str = "product") -> None:
        self._entries[event.event_id] = OutboxEntry(
            id=event.event_id,
            tenant_id=event.tenant_id,
            partition_key=event.partition_key,
            event_type=event.event_type,
            payload=event.as_payload(),
            occurred_on=event.occurred_on,
            channel=channel,
            correlation_id=current_correlation_id(),
        )

    def list_unpublished(self, channel: str, limit: int) -> List[OutboxEntry]:
        pending = [
            e for e in self._entries.values()
            if e.channel == channel and e.id not in self.published_ids
        ]
        # Same rule as the real adapter: only the oldest unpublished row of
        # each partition_key is eligible.
        oldest = {}
        for e in sorted(pending, key=lambda e: (e.occurred_on, str(e.id))):
            oldest.setdefault(e.partition_key, e)
        return sorted(oldest.values(), key=lambda e: e.occurred_on)[:limit]

    def mark_published(self, event_id: UUID) -> None:
        self.published_ids.append(event_id)

    def mark_failed(self, event_id: UUID, error: str) -> None:
        # Left off both lists on purpose: a failed entry must still show up
        # in the next list_unpublished() call, same as the real adapter.
        self.failed_ids.append(event_id)


class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(
        self,
        lead_repo: Optional[LeadRepositoryPort] = None,
        rule_repo: Optional[RuleRepositoryPort] = None,
        leads: Optional[LeadRepositoryPort] = None,
        rules: Optional[RuleRepositoryPort] = None,
        groups: Optional[SalesGroupRepositoryPort] = None,
        disqualification_rules: Optional[DisqualificationRuleRepositoryPort] = None,
        outbox: Optional[OutboxRepositoryPort] = None,
        advisors: Optional[InMemoryAdvisorRepository] = None,
    ) -> None:
        # Defaulting to a fresh in-memory repo (instead of None) is what lets
        # a test that only cares about leads and rules write
        # InMemoryUnitOfWork() and go, instead of wiring up every repo by hand.
        self.leads = leads if leads is not None else (lead_repo or InMemoryLeadRepository())
        self.rules = rules if rules is not None else (rule_repo or InMemoryRuleRepository())
        self.advisors = advisors or InMemoryAdvisorRepository()
        # group_id filtering on leads needs each lead's assigned advisor.
        if isinstance(self.leads, InMemoryLeadRepository):
            self.leads.advisor_repo = self.advisors
        self.groups = groups or InMemorySalesGroupRepository()
        if isinstance(self.groups, InMemorySalesGroupRepository):
            self.groups.advisor_repo = self.advisors
        self.disqualification_rules = disqualification_rules or InMemoryDisqualificationRuleRepository()
        self.outbox = outbox or InMemoryOutboxRepository()

    def __enter__(self) -> 'InMemoryUnitOfWork':
        # Only the outbox honours rollback: it is the one write whose survival
        # a test needs to tell apart from the transaction it belongs to.
        if isinstance(self.outbox, InMemoryOutboxRepository):
            self._outbox_snapshot = dict(self.outbox._entries)
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        if isinstance(self.outbox, InMemoryOutboxRepository):
            self.outbox._entries = self._outbox_snapshot
