"""Per-session conversation memory, so that "e con due bagni?" can refer to
the search before it.

Only the user/assistant prose is kept — not the tool blocks. A follow-up
makes the model issue a fresh search, which keeps the stored context small
and cheap while still letting it refer back to references it mentioned.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Callable, Protocol

DEFAULT_TTL_MINUTES = 60
DEFAULT_MAX_TURNS = 20


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


class ConversationStore(Protocol):
    def append(self, session_id: str, turn: Turn) -> None:
        """Record one turn of the conversation."""
        ...

    def history(self, session_id: str) -> list[Turn]:
        """The turns still remembered for that session, oldest first."""
        ...


@dataclass
class _Session:
    turns: deque[Turn]
    last_activity_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InMemoryConversationStore:
    """Single-process store. Swap for a Redis-backed one behind
    `ConversationStore` if the backend is ever run multi-process."""

    def __init__(
        self,
        clock: Callable[[], datetime] = _utc_now,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self._clock = clock
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_turns = max_turns
        self._sessions: dict[str, _Session] = {}

    def append(self, session_id: str, turn: Turn) -> None:
        now = self._clock()
        session = self._live_session(session_id, now)
        if session is None:
            session = _Session(turns=deque(maxlen=self._max_turns), last_activity_at=now)
            self._sessions[session_id] = session

        session.turns.append(turn)
        session.last_activity_at = now

    def history(self, session_id: str) -> list[Turn]:
        session = self._live_session(session_id, self._clock())
        return list(session.turns) if session else []

    def _live_session(self, session_id: str, now: datetime) -> _Session | None:
        """Returns the session unless it has been idle past its TTL, in which
        case it is dropped — expiry is lazy, driven by access."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if now - session.last_activity_at > self._ttl:
            del self._sessions[session_id]
            return None
        return session
