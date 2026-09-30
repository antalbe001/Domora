from datetime import UTC, datetime, timedelta

from app.services.conversation_store import InMemoryConversationStore, Role, Turn


class FakeClock:
    """A clock the test moves by hand, so TTL behaviour needs no sleeping."""

    def __init__(self) -> None:
        self._now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **delta: float) -> None:
        self._now += timedelta(**delta)


def _store(clock: FakeClock, **overrides: int) -> InMemoryConversationStore:
    return InMemoryConversationStore(clock=clock, **overrides)


def test_returns_the_turns_of_a_session_in_order() -> None:
    store = _store(FakeClock())

    store.append("s1", Turn(role=Role.USER, text="trilocali a Pordenone"))
    store.append("s1", Turn(role=Role.ASSISTANT, text="Ne ho trovati 7."))

    assert [(turn.role, turn.text) for turn in store.history("s1")] == [
        (Role.USER, "trilocali a Pordenone"),
        (Role.ASSISTANT, "Ne ho trovati 7."),
    ]


def test_sessions_do_not_see_each_other() -> None:
    store = _store(FakeClock())

    store.append("s1", Turn(role=Role.USER, text="a Pordenone"))
    store.append("s2", Turn(role=Role.USER, text="a Sacile"))

    assert [turn.text for turn in store.history("s1")] == ["a Pordenone"]
    assert [turn.text for turn in store.history("s2")] == ["a Sacile"]


def test_an_unknown_session_has_no_history() -> None:
    assert _store(FakeClock()).history("never-seen") == []


def test_keeps_only_the_most_recent_turns() -> None:
    store = _store(FakeClock(), max_turns=3)

    for index in range(5):
        store.append("s1", Turn(role=Role.USER, text=str(index)))

    assert [turn.text for turn in store.history("s1")] == ["2", "3", "4"]


def test_forgets_a_session_left_idle_past_its_ttl() -> None:
    clock = FakeClock()
    store = _store(clock, ttl_minutes=60)
    store.append("s1", Turn(role=Role.USER, text="a Pordenone"))

    clock.advance(minutes=61)

    assert store.history("s1") == []


def test_activity_keeps_a_session_alive() -> None:
    clock = FakeClock()
    store = _store(clock, ttl_minutes=60)
    store.append("s1", Turn(role=Role.USER, text="primo"))

    clock.advance(minutes=59)
    store.append("s1", Turn(role=Role.USER, text="secondo"))
    clock.advance(minutes=59)

    assert [turn.text for turn in store.history("s1")] == ["primo", "secondo"]
