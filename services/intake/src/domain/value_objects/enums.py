from enum import Enum


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
