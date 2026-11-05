"""Offline tests for the v0.3.0 admission limiter."""

import pytest

from pinterest_bot.rate_limit import DownloadLimiter


@pytest.fixture
def clock():
    now = [100.0]
    return now


def make_limiter(clock, max_concurrent=2, cooldown_seconds=30):
    return DownloadLimiter(max_concurrent, cooldown_seconds, clock=lambda: clock[0])


def test_first_download_allowed(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed


def test_same_user_cannot_start_two_downloads(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    decision = limiter.try_start(101)
    assert not decision.allowed
    assert "already have" in decision.message


def test_two_different_users_can_download(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    assert limiter.try_start(202).allowed


def test_third_user_cannot_exceed_global_limit(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    assert limiter.try_start(202).allowed
    decision = limiter.try_start(303)
    assert not decision.allowed
    assert "busy" in decision.message


def test_finishing_releases_global_slot(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    assert limiter.try_start(202).allowed
    limiter.finish(101)
    assert limiter.try_start(303).allowed


def test_user_cooldown_applies_after_finish(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    limiter.finish(101)
    result = limiter.try_start(101)
    assert not result.allowed
    assert "30 seconds" in result.message


def test_cooldown_expires(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    limiter.finish(101)
    clock[0] += 30
    assert limiter.try_start(101).allowed


def test_cooldown_is_per_user(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    limiter.finish(101)
    assert limiter.try_start(202).allowed


def test_repeated_finish_does_not_change_cooldown(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    limiter.finish(101)
    clock[0] += 10
    limiter.finish(101)
    clock[0] += 20
    assert limiter.try_start(101).allowed


def test_invalid_limits_rejected():
    with pytest.raises(ValueError):
        DownloadLimiter(max_concurrent=0)
    with pytest.raises(ValueError):
        DownloadLimiter(cooldown_seconds=-1)


def test_expired_entries_are_pruned(clock):
    limiter = make_limiter(clock)
    assert limiter.try_start(101).allowed
    limiter.finish(101)
    clock[0] += 31
    for _ in range(200):
        limiter.try_start(101)
    assert limiter._last_finished == {}
