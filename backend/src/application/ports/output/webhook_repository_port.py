from abc import ABC, abstractmethod
from typing import List
from domain.webhooks.webhook import WebhookConfig
from domain.value_objects.enums import WebhookEventType


class WebhookRepositoryPort(ABC):
    """Output port for querying tenant webhook configurations."""

    @abstractmethod
    def get_by_tenant_and_event(
        self, tenant_id: str, event_type: WebhookEventType
    ) -> List[WebhookConfig]:
        """Obtain active webhook configurations for a specific tenant and event type."""
        pass
