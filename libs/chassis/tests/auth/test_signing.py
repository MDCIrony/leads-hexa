import base64

import pytest

from auth.helpers import signer
from chassis.auth import load_signers


def test_load_signers_parses_spec_and_keeps_order():
    seed = base64.urlsafe_b64encode(b"\x01" * 32).rstrip(b"=").decode()
    seed2 = base64.urlsafe_b64encode(b"\x02" * 32).rstrip(b"=").decode()
    signers = load_signers(f"a={seed}, b={seed2}")
    assert [s.kid for s in signers] == ["a", "b"]
    assert signers[0].public_jwk()["kid"] == "a"


@pytest.mark.parametrize("spec", ["", "  ", "nokey", "a=short", "a=AAAA,a=AAAA", "a=" + "****" + "A" * 43])
def test_load_signers_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        load_signers(spec)


def test_public_jwk_shape():
    jwk = signer("k9").public_jwk()
    assert {k: jwk[k] for k in ("kty", "crv", "alg", "use", "kid")} == {
        "kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig", "kid": "k9"}
    assert "d" not in jwk
