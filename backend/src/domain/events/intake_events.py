from dataclasses import dataclass

from domain.events.internal_event import InternalEvent


@dataclass(kw_only=True)
class IntakeJobRequested(InternalEvent):
    """A received job waiting for a worker.

    Recorded in the same transaction as the reception, so a job that exists
    is a job some worker will get, whether or not the broker was up."""

    tenant_id: str
    job_id: str

    @property
    def partition_key(self) -> str:
        return self.job_id


@dataclass(kw_only=True)
class IntakeRejected(InternalEvent):
    """Emitted when an incoming payload fails validation and cannot become a lead."""

    tenant_id: str
    intake_record_id: str
    reason: str

    @property
    def partition_key(self) -> str:
        return self.intake_record_id
