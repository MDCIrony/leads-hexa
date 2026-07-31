from typing import Any, Dict, List
from application.ports.output.webhook_dispatcher_port import WebhookDispatcherPort

class InMemoryWebhookDispatcher(WebhookDispatcherPort):
    def __init__(self) -> None:
        self.dispatched_events: List[Dict[str, Any]] = []

    def dispatch(self, target_url: str, secret_token: str, payload: Dict[str, Any]) -> bool:
        self.dispatched_events.append({
            "target_url": target_url,
            "secret_token": secret_token,
            "payload": payload,
        })
        return True
