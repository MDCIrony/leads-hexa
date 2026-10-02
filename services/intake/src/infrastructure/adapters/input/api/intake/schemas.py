from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestLeadRequest(BaseModel):
    # No format validation on purpose: a 422 here would discard the payload
    # before anything is persisted. A malformed email reaches lead-core, which
    # rejects it while the record stays in the inbox.
    first_name: str
    last_name: str
    email: Optional[str] = None
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    phone: Optional[str] = None


class IntakeAcceptedResponse(BaseModel):
    job_id: str
    record_ids: List[str]
    status: str


class LeadProcessedResponse(BaseModel):
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None
    # The payload this lead came from: answers "what did the client actually send?".
    intake_record_id: str = ""


class IntakeErrorResponse(BaseModel):
    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None


class IntakeRecordResponse(BaseModel):
    id: str
    source_id: str
    status: str
    payload: Dict[str, Any]
    errors: List[IntakeErrorResponse]
    received_at: datetime
    processed_at: Optional[datetime] = None
    lead_id: Optional[str] = None


class IntakeRecordsPageResponse(BaseModel):
    items: List[IntakeRecordResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class PromoteIntakeRecordRequest(BaseModel):
    payload: Dict[str, Any]


class IntakeJobResponse(BaseModel):
    id: str
    source_id: str
    kind: str
    status: str
    # Null until the file is parsed: a batch's total is unknown when it is accepted.
    total_items: Optional[int] = None
    succeeded: int
    failed: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class IntakeJobsPageResponse(BaseModel):
    items: List[IntakeJobResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class IntakeStatsResponse(BaseModel):
    pending: int
    rejected: int
    # What the inbox badge shows: the records that wait for a person or a retry.
    pending_intake: int
