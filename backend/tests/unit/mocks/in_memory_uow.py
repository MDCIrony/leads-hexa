from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.disqualification_rule_repository_port import (
    DisqualificationRuleRepositoryPort,
)
from application.ports.output.intake_job_repository_port import IntakeJobRepositoryPort
from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.notification_repository_port import NotificationRepositoryPort
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.tenant_repository_port import TenantRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import OutboxEntry
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.entities.notification import Notification
from domain.events.lead_events import OutboundEvent
from domain.value_objects.enums import IntakeJobStatus, IntakeRecordStatus
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_lead_source_repo import InMemoryLeadSourceRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_tenant_repo import InMemoryTenantRepository
from application.ports.output.auth_session_repository_port import AuthSessionRepositoryPort
from application.ports.output.auth_challenge_repository_port import AuthChallengeRepositoryPort
from domain.entities.auth_session import AuthSession
from domain.entities.auth_challenge import AuthChallenge
from datetime import datetime


class InMemoryAuthSessionRepository(AuthSessionRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, AuthSession] = {}

    def save(self, session: AuthSession) -> None:
        self.items[session.token_hash] = session

    def get_active(self, token_hash: str, now: datetime) -> Optional[AuthSession]:
        session = self.items.get(token_hash)
        return session if session and session.revoked_at is None and session.expires_at > now else None

    def revoke(self, token_hash: str, now: datetime) -> None:
        session = self.items.get(token_hash)
        if session and session.revoked_at is None:
            self.items[token_hash] = AuthSession(**{**session.__dict__, "revoked_at": now})


class InMemoryAuthChallengeRepository(AuthChallengeRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, AuthChallenge] = {}

    def save(self, challenge: AuthChallenge) -> None:
        self.items[challenge.token_hash] = challenge

    def resolve_active(self, token_hash: str, now: datetime) -> Optional[AuthChallenge]:
        challenge = self.items.get(token_hash)
        return challenge if challenge and challenge.consumed_at is None and challenge.expires_at > now else None

    def increment_attempts(self, token_hash: str, now: datetime) -> bool:
        challenge = self.resolve_active(token_hash, now)
        if not challenge:
            return False
        self.items[token_hash] = AuthChallenge(**{**challenge.__dict__, "attempts": challenge.attempts + 1})
        return True

    def consume(self, token_hash: str, now: datetime) -> bool:
        challenge = self.resolve_active(token_hash, now)
        if not challenge:
            return False
        self.items[token_hash] = AuthChallenge(**{**challenge.__dict__, "consumed_at": now})
        return True


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


class InMemoryNotificationRepository(NotificationRepositoryPort):
    """Kept inline (same convention as the other mocks above)."""

    def __init__(self) -> None:
        self._notifications: Dict[UUID, Notification] = {}

    def save(self, notification: Notification) -> Notification:
        self._notifications[notification.id.value] = notification
        return notification

    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Optional[Notification]:
        notification = self._notifications.get(notification_id)
        return notification if notification and notification.recipient_id.value == recipient_id else None

    def list_by_recipient(
        self,
        recipient_id: UUID,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        items = [
            n
            for n in self._notifications.values()
            if n.recipient_id.value == recipient_id and (not unread_only or not n.is_read)
        ]
        items.sort(key=lambda n: n.created_at, reverse=True)
        return items[offset : offset + limit]

    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int:
        return sum(
            1
            for n in self._notifications.values()
            if n.recipient_id.value == recipient_id and (not unread_only or not n.is_read)
        )

    def mark_all_read(self, recipient_id: UUID) -> int:
        count = 0
        for n in self._notifications.values():
            if n.recipient_id.value == recipient_id and not n.is_read:
                n.mark_as_read()
                count += 1
        return count


class InMemoryOutboxRepository(OutboxRepositoryPort):
    """Kept inline (same convention as the other mocks above)."""

    def __init__(self) -> None:
        self._entries: Dict[UUID, OutboxEntry] = {}
        self.published_ids: List[UUID] = []
        self.failed_ids: List[UUID] = []

    def record(self, event: OutboundEvent) -> None:
        self._entries[event.event_id] = OutboxEntry(
            id=event.event_id,
            tenant_id=event.tenant_id,
            partition_key=event.partition_key,
            event_type=event.event_type,
            payload=event.as_payload(),
            occurred_on=event.occurred_on,
        )

    def list_unpublished(self, limit: int) -> List[OutboxEntry]:
        items = [e for e in self._entries.values() if e.id not in self.published_ids]
        items.sort(key=lambda e: e.occurred_on)
        return items[:limit]

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
        agent_repo: Optional[AgentRepositoryPort] = None,
        leads: Optional[LeadRepositoryPort] = None,
        rules: Optional[RuleRepositoryPort] = None,
        agents: Optional[AgentRepositoryPort] = None,
        tenants: Optional[TenantRepositoryPort] = None,
        groups: Optional[SalesGroupRepositoryPort] = None,
        sources: Optional[LeadSourceRepositoryPort] = None,
        intake_records: Optional[IntakeRecordRepositoryPort] = None,
        intake_jobs: Optional[IntakeJobRepositoryPort] = None,
        disqualification_rules: Optional[DisqualificationRuleRepositoryPort] = None,
        notifications: Optional[NotificationRepositoryPort] = None,
        outbox: Optional[OutboxRepositoryPort] = None,
    ) -> None:
        # Defaulting to a fresh in-memory repo (instead of None) is what lets
        # a test that only cares about leads and agents write
        # InMemoryUnitOfWork() and go, instead of wiring up every repo by hand.
        self.leads = leads if leads is not None else (lead_repo or InMemoryLeadRepository())
        self.rules = rules if rules is not None else (rule_repo or InMemoryRuleRepository())
        self.agents = agents if agents is not None else (agent_repo or InMemoryAgentRepository())
        # group_id filtering on leads needs each lead's assigned agent.
        if isinstance(self.leads, InMemoryLeadRepository) and isinstance(self.agents, InMemoryAgentRepository):
            self.leads.agent_repo = self.agents
        self.tenants = tenants or InMemoryTenantRepository()
        self.groups = groups or InMemorySalesGroupRepository()
        self.sources = sources or InMemoryLeadSourceRepository()
        self.intake_records = intake_records or InMemoryIntakeRecordRepository()
        self.intake_jobs = intake_jobs or InMemoryIntakeJobRepository()
        self.disqualification_rules = disqualification_rules or InMemoryDisqualificationRuleRepository()
        self.notifications = notifications or InMemoryNotificationRepository()
        self.outbox = outbox or InMemoryOutboxRepository()
        self.sessions = InMemoryAuthSessionRepository()
        self.challenges = InMemoryAuthChallengeRepository()

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
