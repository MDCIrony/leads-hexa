from enum import Enum

class Operator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"
    IN = "IN"

class LeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    DISCARDED = "DISCARDED"

class AssignmentStrategy(str, Enum):
    ROUND_ROBIN = "ROUND_ROBIN"
    LOWEST_LOAD = "LOWEST_LOAD"
    DIRECT_AGENT = "DIRECT_AGENT"

class WebhookEventType(str, Enum):
    LEAD_INGESTED = "LEAD_INGESTED"
    LEAD_QUALIFIED = "LEAD_QUALIFIED"
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    LEAD_PROCESSED = "LEAD_PROCESSED"
    PROCESSING_ERROR = "PROCESSING_ERROR"

class AgentRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    AGENT = "AGENT"

class AgentMatchMode(str, Enum):
    """How a rule combines its target group with its named agents.

    ANY is the default because the alternative silently drops a named agent
    that happens to belong to a different group — the caller asked for that
    person explicitly, so excluding them is never what they meant."""

    ANY = "ANY"
    ONLY = "ONLY"

class LeadSourceKind(str, Enum):
    """How a lead reaches the system.

    WEBHOOK is declared here and implemented in F3b: the enum value costs one
    line and avoids reopening the type when the adapter lands."""

    MANUAL_FORM = "MANUAL_FORM"
    FILE_UPLOAD = "FILE_UPLOAD"
    WEBHOOK = "WEBHOOK"

class IntakeRecordStatus(str, Enum):
    """What happened to a payload after it arrived."""

    PENDING = "PENDING"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    DISCARDED = "DISCARDED"

class IntakeJobKind(str, Enum):
    SINGLE = "SINGLE"
    BATCH = "BATCH"


class IntakeJobStatus(str, Enum):
    """How far along an ingestion operation is."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    # Terminal: no work left. NOT a claim that everything succeeded — a job with
    # ten rejected items is COMPLETED with failed=10. "Finished" and "went well"
    # are different questions and the counters answer the second one.
    COMPLETED = "COMPLETED"
    # The job could not even start: unreadable file, missing source.
    FAILED = "FAILED"
