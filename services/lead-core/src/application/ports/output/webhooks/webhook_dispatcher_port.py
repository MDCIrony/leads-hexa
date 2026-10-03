from abc import ABC, abstractmethod
from typing import Any, Dict

class WebhookDispatcherPort(ABC):
    @abstractmethod
    def dispatch(self, target_url: str, secret_token: str, payload: Dict[str, Any]) -> bool:
        """Envía un payload firmado vía HTTP POST al webhook del usuario."""
        pass
