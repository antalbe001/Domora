"""`ChatModel` implemented on the Anthropic Messages API.

Uses a manual loop rather than the SDK's tool runner on purpose: the caller
(`ChatService`) needs to stream text as it arrives *and* surface the listings
each tool returned, which the runner does not expose — and the runner is
still beta.

Text is streamed event by event; the tool calls are then read off
`get_final_message()`, which hands them over with their JSON arguments
already assembled and parsed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator, Protocol, Sequence

import anthropic

from app.llm.chat_model import (
    AssistantMessage,
    ConversationMessage,
    ModelEvent,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    TurnEnd,
    UserMessage,
)
from app.llm.tools import ToolSpec

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 4096
RETRY_BACKOFF_SECONDS = 0.5

# Failures worth one more attempt: nothing about the request is wrong, the
# call just did not get through.
_TRANSIENT_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class _StreamingClient(Protocol):
    """The slice of anthropic.Anthropic this adapter uses."""

    messages: Any


class AnthropicChatModel:
    def __init__(
        self,
        client: _StreamingClient,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._retry_backoff_seconds = retry_backoff_seconds

    def stream(
        self,
        system: str,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolSpec],
    ) -> Iterator[ModelEvent]:
        request = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": _to_api_messages(messages),
            "tools": [_to_api_tool(tool) for tool in tools],
        }

        for attempt in (1, 2):
            produced_output = False
            try:
                with self._client.messages.stream(**request) as stream:
                    for event in stream:
                        if _is_text_delta(event):
                            produced_output = True
                            yield TextDelta(text=event.delta.text)
                    final = stream.get_final_message()
            except _TRANSIENT_ERRORS:
                # Retrying after partial output would duplicate what the user
                # has already read, so only a failure before any output is
                # worth another attempt.
                if attempt == 2 or produced_output:
                    raise
                logger.warning("Anthropic call failed before output; retrying once")
                time.sleep(self._retry_backoff_seconds)
                continue

            for block in final.content:
                if getattr(block, "type", None) == "tool_use":
                    yield ToolCall(id=block.id, name=block.name, input=dict(block.input))
            yield TurnEnd(stop_reason=final.stop_reason)
            return


def _is_text_delta(event: Any) -> bool:
    return (
        getattr(event, "type", None) == "content_block_delta"
        and getattr(event.delta, "type", None) == "text_delta"
    )


def _to_api_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
    }


def _to_api_messages(messages: Sequence[ConversationMessage]) -> list[dict[str, Any]]:
    api_messages: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, UserMessage):
            api_messages.append({"role": "user", "content": message.text})
        elif isinstance(message, AssistantMessage):
            api_messages.append(
                {"role": "assistant", "content": _assistant_content(message)}
            )
        else:
            _append_tool_result(api_messages, message)

    return api_messages


def _assistant_content(message: AssistantMessage) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if message.text:
        blocks.append({"type": "text", "text": message.text})
    blocks.extend(
        {
            "type": "tool_use",
            "id": call.id,
            "name": call.name,
            "input": call.input,
        }
        for call in message.tool_calls
    )
    return blocks


def _append_tool_result(
    api_messages: list[dict[str, Any]], message: ToolResultMessage
) -> None:
    """All results of one parallel round belong in a single user message —
    splitting them teaches the model to stop calling tools in parallel."""
    block = {
        "type": "tool_result",
        "tool_use_id": message.tool_call_id,
        "content": json.dumps(message.payload, ensure_ascii=False),
    }

    last = api_messages[-1] if api_messages else None
    if (
        last is not None
        and last["role"] == "user"
        and isinstance(last["content"], list)
        and last["content"]
        and last["content"][0].get("type") == "tool_result"
    ):
        last["content"].append(block)
        return

    api_messages.append({"role": "user", "content": [block]})
