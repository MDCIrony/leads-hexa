import base64
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chassis.auth import (
    Ed25519Signer, JwksCache, TokenError, TokenVerifier, load_signers,
)

ISS, AUD = "identity", "lead-router"


def _claims(**overrides):
    now = int(time.time())
    base = {"iss": ISS, "aud": AUD, "sub": str(uuid.uuid4()), "tid": str(uuid.uuid4()),
            "role": "MANAGER", "ptype": "human", "iat": now, "exp": now + 60,
            "jti": str(uuid.uuid4())}
    base.update(overrides)
    return base


def _verifier(*signers):
    return TokenVerifier(JwksCache(lambda: {"keys": [s.public_jwk() for s in signers]}),
                         issuer=ISS, audience=AUD)


def _signer(kid="k1"):
    return Ed25519Signer(kid, Ed25519PrivateKey.generate())


def test_round_trip_returns_claims():
    signer = _signer()
    claims = _claims()
    result = _verifier(signer).verify(signer.sign(claims))
    assert (result.sub, result.tid, result.role, result.ptype) == (
        claims["sub"], claims["tid"], "MANAGER", "human")


def test_token_from_another_key_with_same_kid_is_rejected():
    with pytest.raises(TokenError):
        _verifier(_signer("k1")).verify(_signer("k1").sign(_claims()))


@pytest.mark.parametrize("field,value", [("aud", "other"), ("iss", "someone")])
def test_wrong_audience_or_issuer_is_rejected(field, value):
    signer = _signer()
    with pytest.raises(TokenError):
        _verifier(signer).verify(signer.sign(_claims(**{field: value})))


def test_expired_token_is_rejected():
    signer = _signer()
    past = int(time.time()) - 120
    with pytest.raises(TokenError):
        _verifier(signer).verify(signer.sign(_claims(iat=past, exp=past + 60)))


@pytest.mark.parametrize("missing", ["exp", "sub", "jti", "iat"])
def test_missing_required_claim_is_rejected(missing):
    signer = _signer()
    claims = _claims()
    del claims[missing]
    with pytest.raises(TokenError):
        _verifier(signer).verify(signer.sign(claims))


def test_alg_none_is_rejected():
    signer = _signer()
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "kid": "k1"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(_claims()).encode()).rstrip(b"=")
    with pytest.raises(TokenError):
        _verifier(signer).verify(f"{header.decode()}.{body.decode()}.")


def test_hs256_signed_with_the_public_key_is_rejected():
    signer = _signer()
    public_x = signer.public_jwk()["x"]
    forged = jwt.encode(_claims(), public_x, algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        _verifier(signer).verify(forged)


@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c"])
def test_malformed_token_is_rejected(garbage):
    with pytest.raises(TokenError):
        _verifier(_signer()).verify(garbage)


def test_unknown_kid_refetches_once_then_finds_the_new_key():
    old, new = _signer("old"), _signer("new")
    published = {"keys": [old.public_jwk()]}
    calls = []

    def fetch():
        calls.append(1)
        return published

    clock = [100.0]
    cache = JwksCache(fetch, min_refresh_seconds=10, clock=lambda: clock[0])
    verifier = TokenVerifier(cache, issuer=ISS, audience=AUD)
    verifier.verify(old.sign(_claims()))
    published = {"keys": [old.public_jwk(), new.public_jwk()]}
    clock[0] += 11
    verifier.verify(new.sign(_claims()))
    assert len(calls) == 2


def test_unknown_kid_does_not_hammer_the_jwks_endpoint():
    calls = []
    cache = JwksCache(lambda: calls.append(1) or {"keys": []}, min_refresh_seconds=10,
                      clock=lambda: 100.0)
    verifier = TokenVerifier(cache, issuer=ISS, audience=AUD)
    for _ in range(5):
        with pytest.raises(TokenError):
            verifier.verify(_signer("ghost").sign(_claims()))
    assert len(calls) == 1


def test_unreachable_jwks_is_a_token_error():
    def fetch():
        raise OSError("down")
    with pytest.raises(TokenError):
        TokenVerifier(JwksCache(fetch), issuer=ISS, audience=AUD).verify(_signer().sign(_claims()))


def test_load_signers_parses_spec_and_keeps_order():
    seed = base64.urlsafe_b64encode(b"\x01" * 32).rstrip(b"=").decode()
    seed2 = base64.urlsafe_b64encode(b"\x02" * 32).rstrip(b"=").decode()
    signers = load_signers(f"a={seed}, b={seed2}")
    assert [s.kid for s in signers] == ["a", "b"]
    assert signers[0].public_jwk()["kid"] == "a"


@pytest.mark.parametrize("spec", ["", "  ", "nokey", "a=short", "a=AAAA,a=AAAA"])
def test_load_signers_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        load_signers(spec)


def test_public_jwk_shape():
    jwk = _signer("k9").public_jwk()
    assert {k: jwk[k] for k in ("kty", "crv", "alg", "use", "kid")} == {
        "kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig", "kid": "k9"}
    assert "d" not in jwk
