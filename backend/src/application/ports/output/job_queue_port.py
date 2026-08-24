from abc import ABC, abstractmethod
from uuid import UUID


class JobQueuePort(ABC):
    """Hands an intake job to a worker process instead of running it in-line.

    Returns bool instead of raising, unlike every other output port: a broker
    outage is not the caller's fault, and the caller needs to decide whether
    to fall back to in-process work rather than lose the lead."""

    @abstractmethod
    def enqueue_intake_job(self, tenant_id: UUID, job_id: UUID) -> bool:
        """Hand the job to a worker. False if the broker is unreachable, so
        the caller can fall back instead of losing the lead."""
