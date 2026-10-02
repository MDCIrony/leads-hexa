from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass(frozen=True)
class IngestLeadCommand:
    """One candidate as it arrived. Values are untyped on purpose: a stored
    payload carries whatever the client or the file parser produced."""

    tenant_id: UUID
    source_id: UUID
    first_name: Any = None
    last_name: Any = None
    company: Any = None
    budget: Any = None
    industry: Any = None
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Any = None
    email: Any = None


@dataclass(frozen=True)
class ReceiveIntakeCommand:
    tenant_id: UUID
    kind: str  # IntakeJobKind as str: DTOs do not import domain enums
    # A list because a single lead sends one payload and a batch sends none yet:
    # its file is parsed by the worker.
    payloads: List[Dict[str, Any]]
    filename: Optional[str] = None
    content: Optional[bytes] = None


@dataclass(frozen=True)
class ReceiveIntakeResult:
    job_id: str
    record_ids: List[str]
    status: str


@dataclass(frozen=True)
class StoredIntakeFile:
    """An uploaded file as received, kept before anything parses it."""

    job_id: UUID
    tenant_id: UUID
    filename: str
    content: bytes
    parsed_at: Optional[datetime] = None
