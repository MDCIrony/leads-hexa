from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import UUID

from domain.sources.lead_source import LeadSource


@dataclass(frozen=True)
class CreateLeadSourceCommand:
    tenant_id: UUID
    name: str
    kind: str
    field_mapping: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class UpdateLeadSourceCommand:
    tenant_id: UUID
    source_id: UUID
    # None means unchanged, so a PATCH can send only what it edits.
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class GetLeadSourcesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class LeadSourcesPageResult:
    items: List[LeadSource]
    total: int
