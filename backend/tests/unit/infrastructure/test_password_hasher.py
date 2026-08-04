from infrastructure.security.password_hasher import hash_password, verify_password


def test_hash_password_returns_a_different_string_than_the_input():
    hashed = hash_password("correct-password-123")
    assert hashed != "correct-password-123"
    assert len(hashed) > 0


def test_verify_password_accepts_the_correct_plaintext():
    hashed = hash_password("correct-password-123")
    assert verify_password("correct-password-123", hashed) is True


def test_verify_password_rejects_the_wrong_plaintext():
    hashed = hash_password("correct-password-123")
    assert verify_password("wrong-password", hashed) is False
