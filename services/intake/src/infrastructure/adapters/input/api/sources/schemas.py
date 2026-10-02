from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from domain.value_objects.enums import LeadSourceKind


class LeadSourceCreate(BaseModel):
    name: str
    kind: LeadSourceKind
    field_mapping: Optional[Dict[str, str]] = None


class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class LeadSourceResponse(BaseModel):
    id: str
    name: str
    kind: str
    field_mapping: Dict[str, str]
    is_active: bool
    created_at: datetime


class PaginatedSourcesResponse(BaseModel):
    items: List[LeadSourceResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
