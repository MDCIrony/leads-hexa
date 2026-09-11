from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AgentMfa:
    agent_id: UUID
    secret_ciphertext: str
    enabled_at: datetime | None = None
    last_used_step: int | None = None
