from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from domain.entities.auth_challenge import AuthChallenge
from domain.exceptions import InvalidAuthChallengeException
from tests.unit.mocks.in_memory_uow import InMemoryAuthChallengeRepository


def _challenge(token_hash="hash", purpose="LOGIN", attempts=0, now=None, expired=False, consumed=False):
    now = now or datetime.now(timezone.utc)
    return AuthChallenge(
        token_hash,
        uuid4(),
        purpose,
        attempts,
        now - timedelta(minutes=1) if expired else now + timedelta(minutes=5),
        now if consumed else None,
        now - timedelta(minutes=5),
    )


def test_create_persists_hash_agent_purpose_and_dates():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    agent_id = uuid4()
    challenge = AuthChallenge("hash", agent_id, "LOGIN", 0, now + timedelta(minutes=5), None, now)
    repo.save(challenge)

    resolved = repo.resolve_active("hash", now)
    assert resolved is not None
    assert resolved.token_hash == "hash"
    assert resolved.agent_id == agent_id
    assert resolved.purpose == "LOGIN"
    assert resolved.attempts == 0
    assert resolved.consumed_at is None
    assert resolved.expires_at > now


def test_resolve_with_an_altered_token_returns_none():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=now))

    assert repo.resolve_active("hash-tampered", now) is None


def test_resolve_of_an_expired_challenge_returns_none():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=now, expired=True))

    assert repo.resolve_active("hash", now) is None


def test_resolve_of_a_consumed_challenge_returns_none():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=now, consumed=True))

    assert repo.resolve_active("hash", now) is None


def test_empty_purpose_is_rejected_at_creation():
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidAuthChallengeException):
        AuthChallenge("hash", uuid4(), "   ", 0, now + timedelta(minutes=5), None, now)


def test_negative_attempts_are_rejected_at_creation():
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidAuthChallengeException):
        AuthChallenge("hash", uuid4(), "LOGIN", -1, now + timedelta(minutes=5), None, now)


def test_distinct_purposes_never_share_a_challenge():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("login-hash", purpose="LOGIN", now=now))
    repo.save(_challenge("mfa-hash", purpose="MFA", now=now))

    assert repo.resolve_active("login-hash", now).purpose == "LOGIN"
    assert repo.resolve_active("mfa-hash", now).purpose == "MFA"


def test_increment_moves_attempts_by_exactly_one():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", attempts=2, now=now))

    assert repo.increment_attempts("hash", now) is True
    assert repo.resolve_active("hash", now).attempts == 3


def test_increment_only_touches_a_live_challenge():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("expired", now=now, expired=True))
    repo.save(_challenge("consumed", now=now, consumed=True))

    assert repo.increment_attempts("expired", now) is False
    assert repo.increment_attempts("consumed", now) is False
    assert repo.increment_attempts("missing", now) is False


def test_consume_fixes_consumed_at_exactly_once():
    first = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=first))

    assert repo.consume("hash", first) is True
    assert repo.consume("hash", first + timedelta(seconds=30)) is False
    assert repo.items["hash"].consumed_at == first


def test_consume_of_an_expired_challenge_fails():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=now, expired=True))

    assert repo.consume("hash", now) is False


def test_challenge_is_atomic_single_use_and_counts_attempts():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(AuthChallenge("hash", uuid4(), "LOGIN", 0, now + timedelta(minutes=5), None, now))

    assert repo.resolve_active("hash", now)
    assert repo.increment_attempts("hash", now)
    assert repo.resolve_active("hash", now).attempts == 1
    assert repo.consume("hash", now)
    assert not repo.consume("hash", now)
    assert repo.resolve_active("hash", now) is None


def test_validation_errors_carry_no_secret():
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidAuthChallengeException) as empty:
        AuthChallenge("s3cr3t-token-hash", uuid4(), "", 0, now + timedelta(minutes=5), None, now)
    with pytest.raises(InvalidAuthChallengeException) as negative:
        AuthChallenge("s3cr3t-token-hash", uuid4(), "LOGIN", -1, now + timedelta(minutes=5), None, now)

    assert "s3cr3t" not in str(empty.value)
    assert "s3cr3t" not in str(negative.value)


def test_oauth_challenge_requires_its_metadata_and_is_consumed_only_for_matching_state():
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidAuthChallengeException):
        AuthChallenge("hash", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now)
    challenge = AuthChallenge(
        "hash", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now,
        provider="GOOGLE", state_hash="state", pkce_verifier="verifier", return_path="/home",
    )
    repo = InMemoryAuthChallengeRepository()
    repo.save(challenge)

    assert repo.consume_oauth("hash", "GOOGLE", "other", now) is None
    assert repo.consume_oauth("hash", "GOOGLE", "state", now) is not None
    assert repo.consume_oauth("hash", "GOOGLE", "state", now) is None


@pytest.mark.parametrize("return_path", ["//other.test", "https://other.test", "/home?next=x", "/home#top", "/home\\other", "/home\x00"])
def test_oauth_challenge_rejects_non_internal_return_paths(return_path):
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidAuthChallengeException):
        AuthChallenge(
            "hash", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now,
            provider="GOOGLE", state_hash="state", pkce_verifier="verifier", return_path=return_path,
        )
