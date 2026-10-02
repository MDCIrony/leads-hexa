"""TestClient that stands in for the gateway and identity in front of the API (ADR-0032).

A test names who is calling with `as_principal(...)`, which is what a session
cookie or an integration key resolves to once identity has introspected it.
The client mints the internal bearer from it with the test signer and forwards
nothing else of the caller's: a client-supplied bearer, key or cookie never
reaches the service, as with nginx. No principal means no bearer, so the app
answers 401 the way it does behind a gateway that found no session.

Outbox rows are never drained: they stay unpublished, as with no worker running."""
import json

import httpx
from fastapi.testclient import TestClient

from tests.tokens import mint_token

_PRINCIPAL = "x-test-principal"
_CLIENT_CREDENTIALS = ("authorization", "x-api-key", "cookie", _PRINCIPAL)
_PUBLIC_EXACT = ("/health", "/openapi.json", "/docs")
_NOT_FOUND = {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}


def as_principal(agent_id, tenant_id, role: str = "MANAGER", ptype: str = "human") -> dict:
    """Headers that make the next request arrive as this principal."""
    return {_PRINCIPAL: json.dumps([str(agent_id), str(tenant_id) if tenant_id else None, role, ptype])}


def tenant_of(headers: dict) -> str:
    """The organization of the principal `as_principal` put in these headers."""
    return json.loads(headers[_PRINCIPAL])[1]


def subject_of(headers: dict) -> str:
    """The agent id of that principal: what GET /auth/me answers in the stack."""
    return json.loads(headers[_PRINCIPAL])[0]


class GatewayClient(TestClient):
    def request(self, method, url, **kwargs):
        merged = self._merge_url(url)
        path = merged.path
        headers = httpx.Headers(kwargs.pop("headers", None))

        if path not in _PUBLIC_EXACT and not path.startswith("/api/v1/"):
            return httpx.Response(404, json=_NOT_FOUND, request=httpx.Request(method, merged))

        principal = headers.get(_PRINCIPAL)
        for name in _CLIENT_CREDENTIALS:
            headers.pop(name, None)
        if principal and path not in _PUBLIC_EXACT:
            agent_id, tenant_id, role, ptype = json.loads(principal)
            headers["Authorization"] = f"Bearer {mint_token(agent_id, tenant_id, role, ptype)}"
        # An empty Cookie header stops httpx from adding the client's jar.
        headers["Cookie"] = ""
        kwargs.pop("cookies", None)
        return super().request(method, url, headers=headers, **kwargs)
