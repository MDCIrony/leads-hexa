"""The challenge repository's contract, pinned on the double the use case tests rely on.
The domain's own validation of AuthChallenge lives in tests/unit/domain/sessions."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.sessions.auth_challenge import AuthChallenge
from tests.unit.application.doubles.auth_repositories import InMemoryAuthChallengeRepository


def _challenge(token_hash="hash", purpose="LOGIN", attempts=0, now=None, expired=False, consumed=False):
    now = now or datetime.now(timezone.utc)
    return AuthChallenge(
        token_hash, uuid4(), purpose, attempts,
        now - timedelta(minutes=1) if expired else now + timedelta(minutes=5),
        now if consumed else None,
        now - timedelta(minutes=5),
    )


def test_resolve_returns_only_a_live_challenge_with_the_exact_hash():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("live", now=now))
    repo.save(_challenge("expired", now=now, expired=True))
    repo.save(_challenge("consumed", now=now, consumed=True))

    assert repo.resolve_active("live", now).token_hash == "live"
    assert repo.resolve_active("live-tampered", now) is None
    assert repo.resolve_active("expired", now) is None
    assert repo.resolve_active("consumed", now) is None


def test_distinct_purposes_never_share_a_challenge():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("login-hash", purpose="LOGIN", now=now))
    repo.save(_challenge("mfa-hash", purpose="MFA", now=now))

    assert repo.resolve_active("login-hash", now).purpose == "LOGIN"
    assert repo.resolve_active("mfa-hash", now).purpose == "MFA"


def test_increment_moves_attempts_by_exactly_one_and_only_on_a_live_challenge():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", attempts=2, now=now))
    repo.save(_challenge("expired", now=now, expired=True))
    repo.save(_challenge("consumed", now=now, consumed=True))

    assert repo.increment_attempts("hash", now) is True
    assert repo.resolve_active("hash", now).attempts == 3
    assert repo.increment_attempts("expired", now) is False
    assert repo.increment_attempts("consumed", now) is False
    assert repo.increment_attempts("missing", now) is False


def test_consume_fixes_consumed_at_exactly_once():
    first = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(_challenge("hash", now=first))
    repo.save(_challenge("expired", now=first, expired=True))

    assert repo.consume("hash", first) is True
    assert repo.consume("hash", first + timedelta(seconds=30)) is False
    assert repo.items["hash"].consumed_at == first
    assert repo.consume("expired", first) is False


def test_an_oauth_challenge_is_consumed_only_for_its_state_and_only_once():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(AuthChallenge(
        "hash", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now,
        provider="GOOGLE", state_hash="state", pkce_verifier="verifier", return_path="/home",
    ))

    assert repo.consume_oauth("hash", "GOOGLE", "other", now) is None
    assert repo.consume_oauth("hash", "GOOGLE", "state", now) is not None
    assert repo.consume_oauth("hash", "GOOGLE", "state", now) is None
