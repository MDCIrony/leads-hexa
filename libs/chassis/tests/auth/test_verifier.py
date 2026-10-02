import base64
import json
import time

import jwt
import pytest

from auth.helpers import FakeJwks, claims, signer, verifier, verifier_for
from chassis.auth import KeysUnavailable, TokenError


def test_round_trip_returns_claims():
    s = signer()
    payload = claims()
    result = verifier(s).verify(s.sign(payload))
    assert (result.sub, result.tid, result.role, result.ptype) == (
        payload["sub"], payload["tid"], "MANAGER", "human")


def test_token_from_another_key_with_same_kid_is_rejected():
    with pytest.raises(TokenError):
        verifier(signer("k1")).verify(signer("k1").sign(claims()))


@pytest.mark.parametrize("field,value", [("aud", "other"), ("iss", "someone")])
def test_wrong_audience_or_issuer_is_rejected(field, value):
    s = signer()
    with pytest.raises(TokenError):
        verifier(s).verify(s.sign(claims(**{field: value})))


def test_expired_token_is_rejected():
    s = signer()
    past = int(time.time()) - 120
    with pytest.raises(TokenError):
        verifier(s).verify(s.sign(claims(iat=past, exp=past + 60)))


@pytest.mark.parametrize("missing", ["exp", "sub", "jti", "iat", "role", "ptype"])
def test_missing_required_claim_is_rejected(missing):
    s = signer()
    payload = claims()
    del payload[missing]
    with pytest.raises(TokenError):
        verifier(s).verify(s.sign(payload))


def test_alg_none_is_rejected():
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "kid": "k1"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(claims()).encode()).rstrip(b"=")
    with pytest.raises(TokenError):
        verifier(signer()).verify(f"{header.decode()}.{body.decode()}.")


def test_hs256_signed_with_the_public_key_is_rejected():
    s = signer()
    forged = jwt.encode(claims(), s.public_jwk()["x"], algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        verifier(s).verify(forged)


@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c"])
def test_malformed_token_is_rejected(garbage):
    with pytest.raises(TokenError):
        verifier(signer()).verify(garbage)


@pytest.mark.parametrize("field,value", [("role", 1), ("ptype", None), ("tid", 7)])
def test_non_string_claims_are_rejected(field, value):
    s = signer()
    with pytest.raises(TokenError):
        verifier(s).verify(s.sign(claims(**{field: value})))


def test_tid_none_round_trips():
    s = signer()
    assert verifier(s).verify(s.sign(claims(tid=None))).tid is None


def test_integration_pair_round_trips():
    s = signer()
    result = verifier(s).verify(s.sign(claims(role="INTEGRATION", ptype="integration")))
    assert (result.role, result.ptype) == ("INTEGRATION", "integration")


@pytest.mark.parametrize("role,ptype", [
    ("MANAGER", "robot"),
    ("INTEGRATION", "human"),
    ("MANAGER", "integration"),
])
def test_unknown_or_incoherent_principal_is_rejected(role, ptype):
    s = signer()
    with pytest.raises(TokenError, match="invalid token claims"):
        verifier(s).verify(s.sign(claims(role=role, ptype=ptype)))


def test_keys_unavailable_leaves_verify_unwrapped():
    s = signer()
    with pytest.raises(KeysUnavailable):
        verifier_for(FakeJwks(error=OSError("down"))).verify(s.sign(claims()))
