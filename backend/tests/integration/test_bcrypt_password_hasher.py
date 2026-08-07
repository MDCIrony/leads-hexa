from application.ports.output.password_hasher_port import PasswordHasherPort
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher


def test_adapter_satisfies_the_port():
    assert isinstance(BcryptPasswordHasher(), PasswordHasherPort)


def test_hash_is_not_the_plaintext():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("s3cret")
    assert hashed != "s3cret"
    assert len(hashed) > 20


def test_verify_accepts_the_original_password():
    hasher = BcryptPasswordHasher()
    assert hasher.verify("s3cret", hasher.hash("s3cret")) is True


def test_verify_rejects_a_different_password():
    hasher = BcryptPasswordHasher()
    assert hasher.verify("wrong", hasher.hash("s3cret")) is False


def test_same_password_hashes_differently_each_time():
    """bcrypt salts every hash, so two calls must not collide."""
    hasher = BcryptPasswordHasher()
    assert hasher.hash("s3cret") != hasher.hash("s3cret")
