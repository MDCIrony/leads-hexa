import uuid
from dataclasses import dataclass
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.enums import WebhookEventType

@dataclass
class WebhookConfig:
    id: uuid.UUID
    tenant_id: TenantId
    event_type: WebhookEventType
    target_url: str
    secret_token: str
