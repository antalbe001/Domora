"""Per-session request allowance.

Every chat message costs a paid model call on a public site, so the cap is
here from the start. A sliding window rather than a fixed one: the allowance
recovers gradually instead of resetting in a burst at the top of each minute.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Callable, Protocol

DEFAULT_MAX_REQUESTS = 10
DEFAULT_PER_SECONDS = 60


class RateLimiter(Protocol):
    def allow(self, key: str) -> bool:
        """True if this request fits within the key's allowance."""
        ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InMemoryRateLimiter:
    def __init__(
        self,
        clock: Callable[[], datetime] = _utc_now,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        per_seconds: int = DEFAULT_PER_SECONDS,
    ) -> None:
        self._clock = clock
        self._max_requests = max_requests
        self._window = timedelta(seconds=per_seconds)
        self._hits: dict[str, deque[datetime]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(key, deque())

        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self._max_requests:
            return False

        hits.append(now)
        return True
