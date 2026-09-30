"""The provider-agnostic port for a streaming, tool-using chat model.

The unit is one assistant *turn*: the caller streams it and only discovers
while it arrives whether it ends in text or in tool calls. That is how the
underlying APIs behave, and it means the orchestration loop does not have to
change to gain or lose streaming.

Messages are neutral: an adapter translates them into whatever content-block
shape its provider wants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol, Sequence

from app.llm.tools import ToolSpec


@dataclass(frozen=True)
class TextDelta:
    """A fragment of the assistant's prose, to be shown as it arrives."""

    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class TurnEnd:
    stop_reason: str


ModelEvent = TextDelta | ToolCall | TurnEnd


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResultMessage:
    tool_call_id: str
    payload: dict[str, Any]


ConversationMessage = UserMessage | AssistantMessage | ToolResultMessage


class ChatModel(Protocol):
    def stream(
        self,
        system: str,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolSpec],
    ) -> Iterator[ModelEvent]:
        """Stream one assistant turn."""
        ...
