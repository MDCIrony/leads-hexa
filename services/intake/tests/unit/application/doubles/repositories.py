"""In-memory repositories with the same observable rules as the SQL ones.

Records and jobs are copied on the way in and out, as a database does: a use case that
forgets `save` must fail its test instead of passing through a shared reference.
"""
import copy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from application.dtos.reception import StoredIntakeFile
from application.ports.output.consumers import ProcessedEventRepositoryPort
from application.ports.output.files import IntakeFileRepositoryPort
from application.ports.output.jobs import IntakeJobRepositoryPort
from application.ports.output.records import IntakeRecordRepositoryPort
from application.ports.output.sources import LeadSourceRepositoryPort
from application.ports.output.tenants import ProvisionedTenantRepositoryPort
from domain.jobs.intake_job import IntakeJob
from domain.records.intake_record import IntakeRecord
from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import IntakeJobStatus, IntakeRecordStatus, LeadSourceKind


class InMemoryLeadSourceRepository(LeadSourceRepositoryPort):
    def __init__(self) -> None:
        self.sources: Dict[UUID, LeadSource] = {}

    def save(self, source: LeadSource) -> LeadSource:
        self.sources[source.id.value] = source
        return source

    def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]:
        source = self.sources.get(source_id)
        return source if source and source.tenant_id.value == tenant_id else None

    def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]:
        return next((s for s in self.sources.values() if s.tenant_id.value == tenant_id and s.kind == kind), None)

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]:
        items = sorted((s for s in self.sources.values() if s.tenant_id.value == tenant_id),
                       key=lambda s: (s.name, str(s.id)))
        return items[offset:offset + limit]

    def delete(self, source_id: UUID, tenant_id: UUID) -> bool:
        if self.get_by_id_and_tenant(source_id, tenant_id) is None:
            return False
        del self.sources[source_id]
        return True


class InMemoryIntakeRecordRepository(IntakeRecordRepositoryPort):
    def __init__(self) -> None:
        self._records: Dict[UUID, IntakeRecord] = {}

    def save(self, record: IntakeRecord) -> IntakeRecord:
        self._records[record.id.value] = copy.deepcopy(record)
        return record

    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        record = self._records.get(record_id)
        return copy.deepcopy(record) if record and record.tenant_id.value == tenant_id else None

    def claim_unpromoted(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        # A single-threaded double cannot race with itself: the status check is the whole behaviour.
        record = self.get_by_id_and_tenant(record_id, tenant_id)
        return record if record and record.status in (IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED) else None

    def _matching(self, tenant_id: UUID, status: Optional[IntakeRecordStatus], job_id: Optional[UUID]):
        return [
            copy.deepcopy(r) for r in self._records.values()
            if r.tenant_id.value == tenant_id
            and (status is None or r.status == status)
            and (job_id is None or (r.job_id is not None and r.job_id.value == job_id))
        ]

    def list_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None, job_id: Optional[UUID] = None,
        limit: int = 100, offset: int = 0,
    ) -> List[IntakeRecord]:
        # received_at descending with id ascending as tiebreaker, as the SQL orders them.
        matches = sorted(self._matching(tenant_id, status, job_id), key=lambda r: r.id.value)
        matches.sort(key=lambda r: r.received_at, reverse=True)
        return matches[offset:offset + limit]

    def count_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None, job_id: Optional[UUID] = None,
    ) -> int:
        return len(self._matching(tenant_id, status, job_id))

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        return sum(1 for r in self._records.values()
                   if r.tenant_id.value == tenant_id and r.source_id.value == source_id)


class InMemoryIntakeJobRepository(IntakeJobRepositoryPort):
    def __init__(self) -> None:
        self._jobs: Dict[UUID, IntakeJob] = {}

    def save(self, job: IntakeJob) -> IntakeJob:
        self._jobs[job.id.value] = copy.deepcopy(job)
        return job

    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]:
        job = self._jobs.get(job_id)
        return copy.deepcopy(job) if job and job.tenant_id.value == tenant_id else None

    def _matching(self, tenant_id: UUID, status: Optional[IntakeJobStatus]) -> List[IntakeJob]:
        return [copy.deepcopy(j) for j in self._jobs.values()
                if j.tenant_id.value == tenant_id and (status is None or j.status == status)]

    def list_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None, limit: int = 100, offset: int = 0,
    ) -> List[IntakeJob]:
        matches = sorted(self._matching(tenant_id, status), key=lambda j: j.id.value)
        matches.sort(key=lambda j: j.created_at, reverse=True)
        return matches[offset:offset + limit]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int:
        return len(self._matching(tenant_id, status))

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        return sum(1 for j in self._jobs.values()
                   if j.tenant_id.value == tenant_id and j.source_id.value == source_id)


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


class InMemoryProvisionedTenantRepository(ProvisionedTenantRepositoryPort):
    def __init__(self) -> None:
        self.tenant_ids: set = set()

    def mark(self, tenant_id: UUID) -> bool:
        if tenant_id in self.tenant_ids:
            return False
        self.tenant_ids.add(tenant_id)
        return True


class InMemoryProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self) -> None:
        self._seen: set = set()

    def mark(self, consumer: str, event_id: UUID) -> bool:
        if (consumer, event_id) in self._seen:
            return False
        self._seen.add((consumer, event_id))
        return True
