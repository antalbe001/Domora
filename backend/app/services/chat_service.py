"""Orchestrates one question: replay the session, let the model stream turns,
run the tools it asks for, and hand the caller both the prose and the
listings behind it.

The prose is streamed as it arrives, tool calls included — the sentence the
model writes before searching ("Cerco a Pordenone...") is more informative
than a generic spinner, so it is passed straight through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Sequence

from app.domain.listing import Listing
from app.llm.chat_model import (
    AssistantMessage,
    ChatModel,
    ConversationMessage,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    TurnEnd,
    UserMessage,
)
from app.llm.listing_tools import ListingTools
from app.llm.tools import ALL_TOOLS
from app.services.conversation_store import ConversationStore, Role, Turn

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_ROUNDS = 4


@dataclass(frozen=True)
class TextChunk:
    """Prose to append to the answer as it streams."""

    text: str


@dataclass(frozen=True)
class Listings:
    """Listings a tool just returned, for the frontend to render as cards."""

    listings: list[Listing]


ChatEvent = TextChunk | Listings


class ChatService:
    def __init__(
        self,
        model: ChatModel,
        tools: ListingTools,
        store: ConversationStore,
        system_prompt: str,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    ) -> None:
        self._model = model
        self._tools = tools
        self._store = store
        self._system_prompt = system_prompt
        self._max_tool_rounds = max_tool_rounds

    def answer(self, session_id: str, message: str) -> Iterator[ChatEvent]:
        messages: list[ConversationMessage] = [
            *_replay(self._store.history(session_id)),
            UserMessage(text=message),
        ]
        answer_parts: list[str] = []

        for round_number in range(1, self._max_tool_rounds + 1):
            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []

            for event in self._model.stream(self._system_prompt, messages, ALL_TOOLS):
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                    yield TextChunk(text=event.text)
                elif isinstance(event, ToolCall):
                    tool_calls.append(event)

            answer_parts.extend(text_parts)

            if not tool_calls:
                break

            if round_number == self._max_tool_rounds:
                logger.warning(
                    "Stopping session %s after %d tool rounds", session_id, round_number
                )
                break

            messages.append(
                AssistantMessage(text="".join(text_parts), tool_calls=tool_calls)
            )
            for call in tool_calls:
                result = self._tools.execute(call.name, call.input)
                if result.listings:
                    yield Listings(listings=result.listings)
                messages.append(
                    ToolResultMessage(tool_call_id=call.id, payload=result.payload)
                )

        self._store.append(session_id, Turn(role=Role.USER, text=message))
        self._store.append(
            session_id, Turn(role=Role.ASSISTANT, text="".join(answer_parts))
        )


def _replay(history: Sequence[Turn]) -> list[ConversationMessage]:
    """Past turns as messages. Only the prose is replayed: a follow-up makes
    the model search again, which keeps the context small."""
    return [
        UserMessage(text=turn.text)
        if turn.role is Role.USER
        else AssistantMessage(text=turn.text)
        for turn in history
    ]
