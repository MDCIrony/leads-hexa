from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from cryptography.fernet import InvalidToken

from infrastructure.adapters.output.security.totp_mfa_crypto import TotpMfaCrypto

_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def crypto():
    return TotpMfaCrypto(_KEY)


def test_the_secret_round_trips_through_encryption_and_is_not_stored_in_clear(crypto):
    secret = crypto.generate_secret()
    ciphertext = crypto.encrypt(secret)

    assert secret not in ciphertext
    assert crypto.decrypt(ciphertext) == secret


def test_another_key_cannot_decrypt(crypto):
    ciphertext = crypto.encrypt(crypto.generate_secret())

    with pytest.raises(InvalidToken):
        TotpMfaCrypto("ZmVybmV0LWtleS1mb3ItYW5vdGhlci10ZXN0LTMyYnk=").decrypt(ciphertext)


@pytest.mark.parametrize("drift", [-30, 0, 30])
def test_a_code_matches_its_step_within_one_step_of_drift(crypto, drift):
    secret = crypto.generate_secret()
    code = pyotp.TOTP(secret).at(_NOW + timedelta(seconds=drift))

    assert crypto.matching_step(secret, code, _NOW) == int((_NOW + timedelta(seconds=drift)).timestamp()) // 30


def test_a_code_two_steps_away_or_wrong_does_not_match(crypto):
    secret = "JBSWY3DPEHPK3PXP"
    window = {pyotp.TOTP(secret).at(_NOW + timedelta(seconds=drift)) for drift in (-30, 0, 30)}
    wrong = next(code for code in ("000000", "111111", "222222", "333333") if code not in window)

    assert crypto.matching_step(secret, pyotp.TOTP(secret).at(_NOW + timedelta(seconds=90)), _NOW) is None
    assert crypto.matching_step(secret, wrong, _NOW) is None


def test_the_provisioning_uri_names_the_product_and_the_agent(crypto):
    uri = crypto.provisioning_uri("JBSWY3DPEHPK3PXP", "ana@acme.test")

    assert uri.startswith("otpauth://totp/Lead%20Router:ana%40acme.test?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
