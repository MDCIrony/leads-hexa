import hmac
import hashlib
import json
import logging
import time
from typing import Any, Dict
import httpx
from application.ports.output.webhooks.webhook_dispatcher_port import WebhookDispatcherPort

_LOGGER = logging.getLogger(__name__)


class HttpxWebhookDispatcher(WebhookDispatcherPort):
    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def _compute_signature(self, secret_token: str, payload_bytes: bytes, timestamp: int) -> str:
        signature_payload = f"t={timestamp}.".encode("utf-8") + payload_bytes
        mac = hmac.new(secret_token.encode("utf-8"), signature_payload, hashlib.sha256)
        return f"t={timestamp},v1={mac.hexdigest()}"

    def dispatch(self, target_url: str, secret_token: str, payload: Dict[str, Any]) -> bool:
        timestamp = int(time.time())
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = self._compute_signature(secret_token, payload_bytes, timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-LeadRouter-Signature": signature,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(target_url, content=payload_bytes, headers=headers)
                return response.status_code in (200, 201, 202, 204)
        except Exception:
            _LOGGER.warning("Webhook dispatch to %s failed", target_url, exc_info=True)
            return False
