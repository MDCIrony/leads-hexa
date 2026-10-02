"""A scripted lead-core and identity behind an httpx.MockTransport, serving the shared fixtures."""
import json

import httpx
from chassis.auth import ServiceTokenClient
from chassis.testing.contracts import load_fixture

from infrastructure.adapters.output.admissions.lead_core_client import LeadCoreClient, correlated_post

LEAD_CORE = "http://lead-core:8000"
IDENTITY = "http://identity:8000"
TOKEN = load_fixture("identity/service-token.v1.json")


class LeadCore:
    """`answer` is called with each request to /internal/v1/admissions and returns its response."""

    def __init__(self, answer=None, fail: Exception | None = None, token_status: int = 200) -> None:
        self.answer, self.fail, self.token_status = answer, fail, token_status
        self.token_requests: list[httpx.Request] = []
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/v1/service-tokens":
            self.token_requests.append(request)
            return httpx.Response(self.token_status, json=TOKEN)
        self.calls.append(request)
        if self.fail:
            raise self.fail
        return self.answer(request)

    def token_bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.token_requests]


def respond(status: int = 200, body=None, content: bytes | None = None):
    return lambda _: httpx.Response(status, json=body) if content is None else httpx.Response(status, content=content)


def client_for(lead_core: LeadCore) -> tuple[LeadCoreClient, ServiceTokenClient]:
    http = httpx.Client(transport=httpx.MockTransport(lead_core))
    tokens = ServiceTokenClient(f"{IDENTITY}/internal/v1/service-tokens", "intake", "secret", "lead-core",
                                post=correlated_post(http.post))
    return LeadCoreClient(LEAD_CORE, tokens, http), tokens
