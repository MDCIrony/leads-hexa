import pytest

from auth.helpers import FakeClock, FakeJwks, signer
from chassis.auth import JwksCache, KeysUnavailable, TokenError


class _ForbiddenLock:
    def __enter__(self):
        raise AssertionError("the fast path must not take the lock")

    def __exit__(self, *exc):
        return False


def _cache(fetch, clock, **options):
    return JwksCache(fetch, clock=clock, **options)


def test_keys_unavailable_is_a_token_error():
    assert isinstance(KeysUnavailable(), TokenError)


def test_known_fresh_kid_needs_neither_fetch_nor_lock():
    fetch, clock = FakeJwks(signer("known")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("known")
    cache._lock = _ForbiddenLock()
    clock.now += 59
    cache.key("known")
    assert fetch.calls == 1


def test_unknown_kid_fetches_once_and_returns_the_key():
    old, new = signer("old"), signer("new")
    fetch, clock = FakeJwks(old), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    fetch.document = FakeJwks(old, new).document
    clock.now += 11
    assert cache.key("new") is not None
    assert fetch.calls == 2


def test_unknown_kid_absent_from_a_document_fetched_in_the_call_is_a_token_error():
    fetch, clock = FakeJwks(signer("old")), FakeClock()
    cache = _cache(fetch, clock)
    with pytest.raises(TokenError, match="unknown signing key") as raised:
        cache.key("ghost")
    assert not isinstance(raised.value, KeysUnavailable)
    assert fetch.calls == 1


def test_unknown_kid_inside_min_refresh_is_keys_unavailable_without_fetch():
    fetch, clock = FakeJwks(signer("old")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    clock.now += 5
    with pytest.raises(KeysUnavailable):
        cache.key("ghost")
    assert fetch.calls == 1


def test_a_flood_of_invented_kids_fetches_at_most_once_per_min_refresh():
    fetch, clock = FakeJwks(signer("old")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    for second in range(9):
        clock.now += 1
        with pytest.raises(KeysUnavailable):
            cache.key(f"ghost-{second}")
    assert fetch.calls == 1


def test_rotation_after_a_failed_refresh_is_503_then_retried_after_cold_retry():
    old, new = signer("old"), signer("new")
    fetch, clock = FakeJwks(old), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    fetch.error = OSError("down")
    clock.now += 60
    assert cache.key("old") is not None
    clock.now += 3
    with pytest.raises(KeysUnavailable):
        cache.key("new")
    fetch.error, fetch.document = None, FakeJwks(old, new).document
    clock.now += 1.1
    assert cache.key("new") is not None
    assert fetch.calls == 4


def test_rotation_right_after_a_successful_refresh_is_503_never_401():
    old, new = signer("old"), signer("new")
    fetch, clock = FakeJwks(old), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    clock.now += 60
    cache.key("old")
    fetch.document = FakeJwks(old, new).document
    clock.now += 4
    with pytest.raises(KeysUnavailable):
        cache.key("new")
    assert fetch.calls == 2
    clock.now += 6
    assert cache.key("new") is not None


def test_failed_cold_fetch_is_retried_after_cold_retry():
    s = signer("k1")
    fetch, clock = FakeJwks(s, error=OSError("down")), FakeClock()
    cache = _cache(fetch, clock)
    with pytest.raises(KeysUnavailable):
        cache.key("k1")
    clock.now += 0.5
    with pytest.raises(KeysUnavailable):
        cache.key("k1")
    assert fetch.calls == 1
    fetch.error = None
    clock.now += 0.6
    assert cache.key("k1") is not None
    assert fetch.calls == 2


def test_known_kid_past_max_age_is_refetched():
    fetch, clock = FakeJwks(signer("k1")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("k1")
    clock.now += 61
    cache.key("k1")
    assert fetch.calls == 2


def test_rotated_out_kid_is_rejected_after_max_age():
    fetch, clock = FakeJwks(signer("old")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("old")
    fetch.document = FakeJwks(signer("new")).document
    clock.now += 61
    with pytest.raises(TokenError, match="unknown signing key"):
        cache.key("old")


def test_stale_known_kid_is_served_when_refresh_fails(caplog):
    fetch, clock = FakeJwks(signer("k1")), FakeClock()
    cache = _cache(fetch, clock)
    first = cache.key("k1")
    fetch.error = OSError("down")
    clock.now += 61
    assert cache.key("k1") is first
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    assert fetch.calls == 2


def test_stale_kid_is_served_without_hammering_while_refresh_keeps_failing():
    fetch, clock = FakeJwks(signer("k1")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("k1")
    fetch.error = OSError("down")
    clock.now += 61
    cache.key("k1")
    cache.key("k1")
    assert fetch.calls == 2


def test_unknown_kid_with_a_failing_refresh_is_keys_unavailable():
    fetch, clock = FakeJwks(signer("k1")), FakeClock()
    cache = _cache(fetch, clock)
    cache.key("k1")
    fetch.error = OSError("down")
    clock.now += 11
    with pytest.raises(KeysUnavailable):
        cache.key("ghost")
    assert cache.key("k1") is not None


@pytest.mark.parametrize("document", ["not-a-dict", [], {"keys": [{"kty": "OKP", "crv": "Ed25519",
                                                                    "kid": "x", "x": "***"}]}])
def test_malformed_document_keeps_known_keys(document):
    fetch, clock = FakeJwks(signer("k1")), FakeClock()
    cache = _cache(fetch, clock)
    first = cache.key("k1")
    fetch.document = document
    clock.now += 61
    assert cache.key("k1") is first


@pytest.mark.parametrize("document", ["not-a-dict", [], {"keys": [{"kty": "OKP", "crv": "Ed25519",
                                                                    "kid": "x", "x": "AAAA"}]}])
def test_malformed_document_with_an_empty_cache_is_keys_unavailable(document):
    fetch = FakeJwks()
    fetch.document = document
    with pytest.raises(KeysUnavailable):
        _cache(fetch, FakeClock()).key("k1")
