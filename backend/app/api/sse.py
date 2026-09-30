"""Server-Sent Events encoding for the chat stream.

Three event names reach the frontend: `text` for prose to append, `listings`
for the cards behind an answer, `error` for a failure to show in the chat, and
`done` to close. A failure mid-stream is an `error` event, never a bare 500 —
by then the response has already begun.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable, Iterator

from app.services.chat_service import ChatEvent, Listings, TextChunk

logger = logging.getLogger(__name__)

GENERIC_ERROR_MESSAGE = (
    "Si è verificato un problema nel rispondere. Riprova tra qualche istante."
)


def _encode(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def to_sse(events: Iterable[ChatEvent]) -> Iterator[str]:
    try:
        for event in events:
            if isinstance(event, TextChunk):
                yield _encode("text", {"text": event.text})
            elif isinstance(event, Listings):
                yield _encode(
                    "listings",
                    {
                        "listings": [
                            listing.model_dump(mode="json") for listing in event.listings
                        ]
                    },
                )
    except Exception:
        # The visitor gets a usable sentence; the cause stays in the logs.
        logger.exception("Chat stream failed")
        yield _encode("error", {"message": GENERIC_ERROR_MESSAGE})

    yield _encode("done", {})
