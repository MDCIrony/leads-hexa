from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from domain.jobs.intake_job import IntakeJob


@dataclass(frozen=True)
class GetIntakeJobsQuery:
    tenant_id: UUID
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class IntakeJobsPageResult:
    items: List[IntakeJob]
    total: int
