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
