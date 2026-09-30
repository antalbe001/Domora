from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_chat_service, get_rate_limiter
from app.domain.listing import Listing, PropertyTransaction
from app.main import create_app
from app.services.chat_service import ChatEvent, Listings, TextChunk


class StubChatService:
    def __init__(self, *events: ChatEvent, error: Exception | None = None) -> None:
        self._events = list(events)
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def answer(self, session_id: str, message: str) -> Iterator[ChatEvent]:
        self.calls.append((session_id, message))
        yield from self._events
        if self._error is not None:
            raise self._error


class StubRateLimiter:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    def allow(self, key: str) -> bool:
        return self._allowed


def _listing(reference: str) -> Listing:
    return Listing(
        reference=reference,
        transaction=PropertyTransaction.SALE,
        title=f"{reference} – Appartamento",
        url=f"https://example.test/annunci/{reference.lower()}/",
        price_eur=120_000,
    )


def _client(
    chat_service: Any = None, rate_limiter: Any = None
) -> tuple[TestClient, Any]:
    service = chat_service or StubChatService(TextChunk(text="ok"))
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter or StubRateLimiter()
    return TestClient(app), service


def _ask(client: TestClient, **body: Any) -> Any:
    payload = {"session_id": "s1", "message": "case a Pordenone"}
    payload.update(body)
    return client.post("/api/chat", json=payload)


def test_streams_the_answer_as_server_sent_events() -> None:
    client, service = _client(
        StubChatService(TextChunk(text="Ne ho "), TextChunk(text="trovato 1."))
    )

    response = _ask(client)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Ne ho " in response.text
    assert "trovato 1." in response.text
    assert service.calls == [("s1", "case a Pordenone")]


def test_streams_the_listings_behind_the_answer() -> None:
    client, _ = _client(StubChatService(Listings(listings=[_listing("V1")])))

    body = _ask(client).text

    assert "listings" in body
    assert "V1" in body


def test_signals_the_end_of_the_stream() -> None:
    client, _ = _client()

    assert "event: done" in _ask(client).text


@pytest.mark.parametrize("message", ["", "   ", "x" * 501])
def test_refuses_an_empty_or_oversized_message(message: str) -> None:
    client, _ = _client()

    assert _ask(client, message=message).status_code == 422


def test_refuses_a_request_over_the_rate_limit() -> None:
    client, _ = _client(rate_limiter=StubRateLimiter(allowed=False))

    assert _ask(client).status_code == 429


def test_a_failing_model_becomes_an_error_event_not_a_crash() -> None:
    client, _ = _client(
        StubChatService(TextChunk(text="Cerco..."), error=RuntimeError("anthropic down"))
    )

    response = _ask(client)

    assert response.status_code == 200
    assert "event: error" in response.text
    # The failure reason never reaches the visitor.
    assert "anthropic down" not in response.text
