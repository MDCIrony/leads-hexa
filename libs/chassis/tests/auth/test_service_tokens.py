import threading
import time
import uuid

import pytest

from auth.helpers import FakeClock, FakeJwks, claims, signer, verifier
from chassis.auth import (ISSUER, JwksCache, KeysUnavailable, ServiceTokenClient, ServiceTokenUnavailable,
                          ServiceTokenVerifier, TokenError)

SECRET = "s3cr3t-never-shown"


def service_claims(**overrides):
    now = int(time.time())
    base = {"iss": ISSUER, "aud": "identity", "sub": "lead-core", "ptype": "service",
            "iat": now, "exp": now + 300, "jti": str(uuid.uuid4())}
    base.update(overrides)
    return base


def service_verifier(fetch, audience="identity"):
    return ServiceTokenVerifier(JwksCache(fetch), audience=audience)


def test_valid_service_token_returns_its_claims():
    s = signer()
    payload = service_claims()
    result = service_verifier(FakeJwks(s)).verify(s.sign(payload), {"lead-core"})
    assert (result.sub, result.aud, result.jti, result.exp) == (
        "lead-core", "identity", payload["jti"], payload["exp"])


@pytest.mark.parametrize("overrides,allowed", [
    ({"aud": "lead-core"}, {"lead-core"}),
    ({"sub": "intake"}, {"lead-core"}),
    ({"ptype": "human"}, {"lead-core"}),
    ({"ptype": "integration", "role": "INTEGRATION"}, {"lead-core"}),
    ({"ptype": None}, {"lead-core"}),
    ({"iss": "someone"}, {"lead-core"}),
    ({}, set()),
])
def test_anything_but_an_allowed_service_token_is_rejected(overrides, allowed):
    s = signer()
    payload = {k: v for k, v in service_claims(**overrides).items() if v is not None}
    with pytest.raises(TokenError):
        service_verifier(FakeJwks(s)).verify(s.sign(payload), allowed)


def test_a_human_token_never_passes_as_a_service_token():
    s = signer()
    with pytest.raises(TokenError, match="not a service token"):
        service_verifier(FakeJwks(s), audience="lead-router").verify(s.sign(claims()), {claims()["sub"]})


@pytest.mark.parametrize("extra", [{}, {"role": "MANAGER", "tid": None}])
def test_a_service_token_never_passes_the_human_verifier(extra):
    s = signer()
    with pytest.raises(TokenError):
        verifier(s).verify(s.sign(service_claims(aud="lead-router", **extra)))


def test_expired_service_token_is_rejected():
    s = signer()
    past = int(time.time()) - 400
    with pytest.raises(TokenError):
        service_verifier(FakeJwks(s)).verify(s.sign(service_claims(iat=past, exp=past + 300)), {"lead-core"})


def test_unknown_kid_that_cannot_be_checked_is_keys_unavailable():
    with pytest.raises(KeysUnavailable):
        service_verifier(FakeJwks(error=OSError("down"))).verify(signer().sign(service_claims()), {"lead-core"})


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = {"access_token": "tok-1", "expires_in": 300} if body is None else body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakePost:
    def __init__(self, *responses, delay=0.0):
        self.responses = list(responses) or [FakeResponse()]
        self.calls = []
        self.delay = delay

    def __call__(self, url, json):
        self.calls.append((url, json))
        time.sleep(self.delay)
        response = self.responses[min(len(self.calls), len(self.responses)) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def client(post, clock=None):
    return ServiceTokenClient("http://identity:8000/internal/v1/service-tokens", "lead-core", SECRET,
                              "identity", post=post, clock=clock or FakeClock())


def test_client_posts_its_credentials_and_caches_the_token():
    post, clock = FakePost(), FakeClock()
    c = client(post, clock)
    assert c.token() == "tok-1"
    clock.now += 269
    assert c.token() == "tok-1"
    assert post.calls == [("http://identity:8000/internal/v1/service-tokens",
                           {"client_id": "lead-core", "client_secret": SECRET, "audience": "identity"})]


def test_client_renews_once_less_than_30_seconds_remain():
    post = FakePost(FakeResponse(), FakeResponse(body={"access_token": "tok-2", "expires_in": 300}))
    clock = FakeClock()
    c = client(post, clock)
    c.token()
    clock.now += 270
    assert c.token() == "tok-2"
    assert len(post.calls) == 2


@pytest.mark.parametrize("response", [
    FakeResponse(401, {"error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"}),
    FakeResponse(500, {}),
    FakeResponse(body={"access_token": 7, "expires_in": 300}),
    FakeResponse(body={"access_token": "t", "expires_in": "300"}),
    FakeResponse(body={"access_token": "t", "expires_in": True}),
    FakeResponse(body={"access_token": "t"}),
    FakeResponse(body=["not", "an", "object"]),
    FakeResponse(body=ValueError("not json")),
    OSError(f"connection refused, body had {SECRET}"),
])
def test_client_failures_are_service_token_unavailable_without_the_secret(response):
    with pytest.raises(ServiceTokenUnavailable) as raised:
        client(FakePost(response)).token()
    assert SECRET not in str(raised.value)
    assert raised.value.__cause__ is None or SECRET not in str(raised.value.__cause__)


def test_client_retries_after_a_failure():
    post = FakePost(OSError("down"), FakeResponse())
    c = client(post)
    with pytest.raises(ServiceTokenUnavailable):
        c.token()
    assert c.token() == "tok-1"


def test_concurrent_callers_share_a_single_post():
    post = FakePost(delay=0.05)
    c = client(post)
    barrier = threading.Barrier(8)
    tokens = []

    def call():
        barrier.wait()
        tokens.append(c.token())

    threads = [threading.Thread(target=call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert tokens == ["tok-1"] * 8
    assert len(post.calls) == 1
