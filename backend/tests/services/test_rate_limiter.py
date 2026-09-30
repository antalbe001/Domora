from datetime import UTC, datetime, timedelta

from app.services.rate_limiter import InMemoryRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **delta: float) -> None:
        self._now += timedelta(**delta)


def test_allows_requests_up_to_the_limit() -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock(), max_requests=3, per_seconds=60)

    assert [limiter.allow("s1") for _ in range(3)] == [True, True, True]


def test_refuses_the_request_over_the_limit() -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock(), max_requests=2, per_seconds=60)

    limiter.allow("s1")
    limiter.allow("s1")

    assert limiter.allow("s1") is False


def test_each_session_has_its_own_allowance() -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock(), max_requests=1, per_seconds=60)

    assert limiter.allow("s1") is True
    assert limiter.allow("s2") is True
    assert limiter.allow("s1") is False


def test_the_allowance_recovers_as_the_window_slides() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock, max_requests=2, per_seconds=60)
    limiter.allow("s1")
    limiter.allow("s1")

    clock.advance(seconds=61)

    assert limiter.allow("s1") is True


def test_only_the_expired_part_of_the_window_is_forgiven() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock, max_requests=2, per_seconds=60)
    limiter.allow("s1")
    clock.advance(seconds=30)
    limiter.allow("s1")

    # 31s later the first request has aged out but the second has not.
    clock.advance(seconds=31)

    assert limiter.allow("s1") is True
    assert limiter.allow("s1") is False
