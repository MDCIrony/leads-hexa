from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import InvalidSocialIdentityException


@dataclass(frozen=True)
class SocialIdentity:
    id: UUID
    agent_id: UUID
    provider: str
    provider_subject: str
    email_at_link: str
    created_at: datetime
    last_login_at: datetime

    def __post_init__(self) -> None:
        if self.provider not in {"GOOGLE", "GITHUB"}:
            raise InvalidSocialIdentityException("Unsupported social provider")
        if not self.provider_subject.strip() or not self.email_at_link.strip():
            raise InvalidSocialIdentityException("Social identity is incomplete")
