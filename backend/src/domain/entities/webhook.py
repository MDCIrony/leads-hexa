import uuid
from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.enums import WebhookEventType

@dataclass
class WebhookConfig:
    id: uuid.UUID
    tenant_id: TenantId
    event_type: WebhookEventType
    target_url: str
    secret_token: str

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        event_type: Union[WebhookEventType, str],
        target_url: str,
        secret_token: str,
        config_id: Optional[Union[str, UUID]] = None,
    ) -> "WebhookConfig":
        tid = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        evt = WebhookEventType(event_type) if isinstance(event_type, str) else event_type
        cid = uuid.UUID(str(config_id)) if config_id else uuid.uuid4()
        return cls(
            id=cid,
            tenant_id=tid,
            event_type=evt,
            target_url=target_url,
            secret_token=secret_token,
        )
