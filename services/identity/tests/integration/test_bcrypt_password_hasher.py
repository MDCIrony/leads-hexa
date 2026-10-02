"""Here rather than in unit/: every call pays bcrypt's cost factor (~250 ms)."""
import bcrypt

from application.ports.output.security import PasswordHasherPort
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher

# Produced once by the backend's passlib CryptContext(schemes=["bcrypt"]): the
# format every hash copied from leads_db has.
_PASSLIB_PASSWORD = "correct horse battery"
_PASSLIB_HASH = "$2b$12$ig3A3gOy8Lb60QtjT6O7u.IVtnqlxOV/ruvpmBEJjaIdJNXDrx17u"


def test_adapter_satisfies_the_port():
    assert isinstance(BcryptPasswordHasher(), PasswordHasherPort)


def test_verifies_a_hash_the_backend_produced():
    hasher = BcryptPasswordHasher()

    assert hasher.verify(_PASSLIB_PASSWORD, _PASSLIB_HASH) is True
    assert hasher.verify("correct horse", _PASSLIB_HASH) is False


def test_verifies_a_hash_made_by_bcrypt_directly():
    hashed = bcrypt.hashpw(b"s3cret", bcrypt.gensalt(12)).decode()

    assert BcryptPasswordHasher().verify("s3cret", hashed) is True


def test_produces_the_same_format_the_backend_did():
    hashed = BcryptPasswordHasher().hash("s3cret")

    assert hashed.startswith("$2b$12$") and len(hashed) == 60
    assert BcryptPasswordHasher().verify("s3cret", hashed) is True
    assert BcryptPasswordHasher().verify("wrong", hashed) is False


def test_same_password_hashes_differently_each_time():
    """bcrypt salts every hash, so two calls must not collide."""
    assert BcryptPasswordHasher().hash("s3cret") != BcryptPasswordHasher().hash("s3cret")


def test_a_stored_value_that_is_not_a_bcrypt_hash_matches_nothing():
    assert BcryptPasswordHasher().verify("s3cret", "not-a-hash") is False
