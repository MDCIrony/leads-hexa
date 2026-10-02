"""TestClient that behaves like the gateway in front of the API (ADR-0031).

Mirrors gateway/nginx.conf: it authenticates through the internal
introspection endpoint and forwards only the resulting bearer, so e2e tests
exercise the same trust boundary the stack runs with. Tests that deliberately
talk to the app without a gateway (test_internal_auth) keep a plain TestClient."""
import httpx
from fastapi.testclient import TestClient

_INTROSPECT = "/internal/v1/auth/introspect"
_PUBLIC_PREFIX = "/api/v1/auth/"
_PUBLIC_EXACT = ("/health", "/openapi.json", "/docs")
_OPTIONAL_PATHS = ("/api/v1/agents", "/api/v1/agents/")
_UNAUTHORIZED = {"error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"}
_NOT_FOUND = {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}


class GatewayClient(TestClient):
    def request(self, method, url, **kwargs):
        merged = self._merge_url(url)
        path = merged.path
        headers = httpx.Headers(kwargs.pop("headers", None))

        is_public = path.startswith(_PUBLIC_PREFIX) or path in _PUBLIC_EXACT
        if not is_public and not path.startswith("/api/v1/"):
            return httpx.Response(404, json=_NOT_FOUND, request=httpx.Request(method, merged))

        if is_public:
            # Public routes see everything but a client-supplied bearer or key.
            for name in ("authorization", "x-api-key"):
                headers.pop(name, None)
            return super().request(method, url, headers=headers, **kwargs)

        introspection_headers = {
            name: headers[name] for name in ("cookie", "x-api-key") if name in headers
        }
        introspection = super().request(
            "GET", _INTROSPECT,
            params={"optional": "true"} if path in _OPTIONAL_PATHS else None,
            headers=introspection_headers, cookies=kwargs.get("cookies"),
        )
        if introspection.status_code == 401:
            return httpx.Response(401, json=_UNAUTHORIZED, request=httpx.Request(method, merged))
        if introspection.status_code not in (200, 204):
            return introspection

        for name in ("authorization", "x-api-key"):
            headers.pop(name, None)
        if introspection.status_code == 200:
            headers["Authorization"] = f"Bearer {introspection.headers['X-Internal-Token']}"
        # An empty Cookie header stops httpx from adding the client's jar: the
        # service must never see the session cookie.
        headers["Cookie"] = ""
        kwargs.pop("cookies", None)
        return super().request(method, url, headers=headers, **kwargs)
