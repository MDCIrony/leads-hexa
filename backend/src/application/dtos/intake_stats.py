from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeStatsResult:
    pending: int
    rejected: int
    # Both still need someone: PENDING waits for processing, REJECTED for a fix.
    pending_intake: int
