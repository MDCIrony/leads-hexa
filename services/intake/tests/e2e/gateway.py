"""TestClient that stands in for the gateway and the intake worker (ADR-0032).

A test names who is calling with `as_principal(...)`, which is what a session cookie
resolves to once identity has introspected it; the client mints the internal bearer
from it with the test signer and forwards nothing else of the caller's, as nginx does.
No principal means no bearer, so the app answers 401.

After every forwarded request it drains the `job` outbox channel in process: what the
relay and RabbitMQ do, then hands each message to the worker's real handler. The wiring is
the container's own; only the admission adapter is replaced, by the fake the container carries."""
import json

import httpx
from fastapi.testclient import TestClient

from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.queue.job_message import job_message
from infrastructure.worker.jobs import process_job_message
from tests.tokens import mint_token

_PRINCIPAL = "x-test-principal"
_CLIENT_CREDENTIALS = ("authorization", "x-api-key", "cookie", _PRINCIPAL)
_NOT_FOUND = {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}
# RabbitMQ's delivery limit on intake.jobs; past it the real message goes to the DLQ.
_MAX_JOB_DELIVERIES = 3


def as_principal(agent_id, tenant_id, role: str = "MANAGER", ptype: str = "human") -> dict:
    """Headers that make the next request arrive as this principal."""
    return {_PRINCIPAL: json.dumps([str(agent_id), str(tenant_id) if tenant_id else None, role, ptype])}


class GatewayClient(TestClient):
    def __init__(self, app, container) -> None:
        super().__init__(app)
        self._container = container

    def request(self, method, url, **kwargs):
        merged = self._merge_url(url)
        headers = httpx.Headers(kwargs.pop("headers", None))
        if not merged.path.startswith("/api/v1/"):
            return httpx.Response(404, json=_NOT_FOUND, request=httpx.Request(method, merged))

        principal = headers.get(_PRINCIPAL)
        for name in _CLIENT_CREDENTIALS:
            headers.pop(name, None)
        if principal:
            agent_id, tenant_id, role, ptype = json.loads(principal)
            headers["Authorization"] = f"Bearer {mint_token(agent_id, tenant_id, role, ptype)}"
        response = super().request(method, url, headers=headers, **kwargs)
        self._drain_jobs()
        return response

    def _drain_jobs(self) -> None:
        """A nack is redelivered up to the queue's limit and then dropped, as the DLQ would."""
        while True:
            with open_outbox_store(self._container.database) as store:
                rows = store.fetch("job", 100)
            if not rows:
                return
            for row in rows:
                # The worker's own message and handler: this client only stands in for the broker.
                message = job_message(row)
                for _ in range(_MAX_JOB_DELIVERIES):
                    if process_job_message(self._container, message) == "ack":
                        break
                with open_outbox_store(self._container.database) as store:
                    store.mark_published(row.id)
