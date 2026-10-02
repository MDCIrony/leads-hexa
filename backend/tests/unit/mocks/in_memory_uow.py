from dataclasses import replace
from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.disqualification_rule_repository_port import (
    DisqualificationRuleRepositoryPort,
)
from application.ports.output.intake_job_repository_port import IntakeJobRepositoryPort
from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from application.ports.output.processed_event_repository_port import ProcessedEventRepositoryPort
from application.ports.output.intake.provisioned_tenant_repository_port import ProvisionedTenantRepositoryPort
from application.ports.output.intake_file_repository_port import IntakeFileRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import OutboxEntry, StoredIntakeFile
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.events.internal_event import InternalEvent
from domain.events.lead_events import OutboundEvent
from domain.value_objects.enums import IntakeJobStatus, IntakeRecordStatus
from infrastructure.adapters.output.persistence.correlation import current_correlation_id
from tests.unit.mocks.in_memory_advisor_repo import InMemoryAdvisorRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_lead_source_repo import InMemoryLeadSourceRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from datetime import datetime, timezone


class InMemoryIntakeRecordRepository(IntakeRecordRepositoryPort):
    """Kept inline (unlike the other mocks) because no other test needs it yet."""

    def __init__(self) -> None:
        self._records: Dict[UUID, IntakeRecord] = {}

    def save(self, record: IntakeRecord) -> IntakeRecord:
        self._records[record.id.value] = record
        return record

    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        record = self._records.get(record_id)
        return record if record and record.tenant_id.value == tenant_id else None

    def claim_unpromoted(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        # No locking to model: a single-threaded double cannot race with
        # itself, so the status check is the whole of the behaviour here.
        record = self.get_by_id_and_tenant(record_id, tenant_id)
        return record if record and record.status != IntakeRecordStatus.PROMOTED else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]:
        matches = [
            r
            for r in self._records.values()
            if r.tenant_id.value == tenant_id
            and (status is None or r.status == status)
            and (job_id is None or (r.job_id is not None and r.job_id.value == job_id))
        ]
        # Stable two-pass sort: tiebreak by id ascending first, then order by
        # received_at descending without disturbing that ascending tiebreak.
        matches.sort(key=lambda r: r.id.value)
        matches.sort(key=lambda r: r.received_at, reverse=True)
        return matches[offset : offset + limit]

    def count_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
    ) -> int:
        return sum(
            1
            for r in self._records.values()
            if r.tenant_id.value == tenant_id
            and (status is None or r.status == status)
            and (job_id is None or (r.job_id is not None and r.job_id.value == job_id))
        )


class InMemoryIntakeJobRepository(IntakeJobRepositoryPort):
    """Kept inline (same convention as InMemoryIntakeRecordRepository above)."""

    def __init__(self) -> None:
        self._jobs: Dict[UUID, IntakeJob] = {}

    def save(self, job: IntakeJob) -> IntakeJob:
        self._jobs[job.id.value] = job
        return job

    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]:
        job = self._jobs.get(job_id)
        return job if job and job.tenant_id.value == tenant_id else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeJobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeJob]:
        matches = [
            j
            for j in self._jobs.values()
            if j.tenant_id.value == tenant_id and (status is None or j.status == status)
        ]
        # Stable two-pass sort: tiebreak by id ascending first, then order by
        # created_at descending without disturbing that ascending tiebreak.
        matches.sort(key=lambda j: j.id.value)
        matches.sort(key=lambda j: j.created_at, reverse=True)
        return matches[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int:
        return sum(
            1
            for j in self._jobs.values()
            if j.tenant_id.value == tenant_id and (status is None or j.status == status)
        )


class InMemoryDisqualificationRuleRepository(DisqualificationRuleRepositoryPort):
    """Kept inline (same convention as the two intake mocks above)."""

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
    """Kept inline (same convention as the other mocks above)."""

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


class InMemoryProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self) -> None:
        self._seen: set = set()

    def mark(self, consumer: str, event_id: UUID) -> bool:
        key = (consumer, event_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


class InMemoryProvisionedTenantRepository(ProvisionedTenantRepositoryPort):
    def __init__(self) -> None:
        self.tenant_ids: set = set()

    def mark(self, tenant_id: UUID) -> bool:
        if tenant_id in self.tenant_ids:
            return False
        self.tenant_ids.add(tenant_id)
        return True


class InMemoryIntakeFileRepository(IntakeFileRepositoryPort):
    def __init__(self) -> None:
        self._files: Dict[UUID, StoredIntakeFile] = {}

    def save(self, job_id: UUID, tenant_id: UUID, filename: str, content: bytes) -> None:
        self._files[job_id] = StoredIntakeFile(job_id, tenant_id, filename, content)

    def get(self, job_id: UUID, tenant_id: UUID) -> Optional[StoredIntakeFile]:
        stored = self._files.get(job_id)
        return stored if stored is not None and stored.tenant_id == tenant_id else None

    def mark_parsed(self, job_id: UUID) -> None:
        stored = self._files.get(job_id)
        if stored is not None:
            self._files[job_id] = replace(stored, parsed_at=datetime.now(timezone.utc))


class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(
        self,
        lead_repo: Optional[LeadRepositoryPort] = None,
        rule_repo: Optional[RuleRepositoryPort] = None,
        leads: Optional[LeadRepositoryPort] = None,
        rules: Optional[RuleRepositoryPort] = None,
        groups: Optional[SalesGroupRepositoryPort] = None,
        sources: Optional[LeadSourceRepositoryPort] = None,
        intake_records: Optional[IntakeRecordRepositoryPort] = None,
        intake_jobs: Optional[IntakeJobRepositoryPort] = None,
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
        self.sources = sources or InMemoryLeadSourceRepository()
        self.intake_records = intake_records or InMemoryIntakeRecordRepository()
        self.intake_jobs = intake_jobs or InMemoryIntakeJobRepository()
        self.disqualification_rules = disqualification_rules or InMemoryDisqualificationRuleRepository()
        self.outbox = outbox or InMemoryOutboxRepository()
        self.processed_events = InMemoryProcessedEventRepository()
        self.intake_files = InMemoryIntakeFileRepository()
        self.provisioned_tenants = InMemoryProvisionedTenantRepository()

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
