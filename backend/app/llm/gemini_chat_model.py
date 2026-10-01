"""`ChatModel` implemented on the Gemini API (`google-genai`).

Verified against the installed SDK's own source (2.26.0), not against
documentation alone — a doc page found while building this described a
different, newer "Interactions" surface with gaps in the exact multi-turn
shape; `client.models.generate_content_stream` is the surface this adapter
actually uses, confirmed by reading `google.genai.models` and `.types`.

Two things differ from the Anthropic adapter and are not just style:

- The plain (non-Enterprise/Vertex) API may leave `function_call.id` unset —
  its own docstring says so. ChatService still needs a stable id to pair a
  tool's result back to the call, so this adapter generates one
  (`call-<n>`) whenever the API doesn't supply it.
- A tool result's `FunctionResponse` must carry the tool's *name*, which our
  neutral `ToolResultMessage` doesn't — only the call id. Since the full
  history is replayed every turn (stateless, like the Anthropic adapter),
  the preceding `AssistantMessage.tool_calls` in that same history always
  carries the name for a given id, so `_to_contents` looks it up there
  rather than needing a new field on the shared type.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterator, Protocol, Sequence

from google.genai import errors as genai_errors
from google.genai import types as genai_types

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

# "-latest" tracks whichever flash model Google currently serves, so this
# default does not 404 the next time a dated model id is retired — which is
# exactly what happened to "gemini-2.0-flash" while verifying this adapter.
DEFAULT_MODEL = "gemini-flash-latest"
RETRY_BACKOFF_SECONDS = 0.5

_FINISH_REASON_MAP = {"STOP": "end_turn", "MAX_TOKENS": "max_tokens"}


class _StreamingClient(Protocol):
    """The slice of genai.Client this adapter uses."""

    models: Any


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, genai_errors.ServerError):
        return True
    return isinstance(error, genai_errors.ClientError) and error.code == 429


class GeminiChatModel:
    def __init__(
        self,
        client: _StreamingClient,
        model: str = DEFAULT_MODEL,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = client
        self._model = model
        self._retry_backoff_seconds = retry_backoff_seconds

    def stream(
        self,
        system: str,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolSpec],
    ) -> Iterator[ModelEvent]:
        request = {
            "model": self._model,
            "contents": _to_contents(messages),
            "config": genai_types.GenerateContentConfig(
                system_instruction=system,
                tools=[_to_tool(tools)] if tools else None,
            ),
        }

        for attempt in (1, 2):
            produced_output = False
            tool_calls: list[ToolCall] = []
            finish_reason: str | None = None
            next_call_index = 1

            try:
                for chunk in self._client.models.generate_content_stream(**request):
                    candidate = chunk.candidates[0]
                    finish_reason = candidate.finish_reason or finish_reason
                    for part in candidate.content.parts:
                        if part.text:
                            produced_output = True
                            yield TextDelta(text=part.text)
                        elif part.function_call:
                            produced_output = True
                            call_id = part.function_call.id
                            if not call_id:
                                call_id = f"call-{next_call_index}"
                                next_call_index += 1
                            tool_calls.append(
                                ToolCall(
                                    id=call_id,
                                    name=part.function_call.name,
                                    input=dict(part.function_call.args or {}),
                                    provider_data=(
                                        {"thought_signature": part.thought_signature}
                                        if part.thought_signature
                                        else None
                                    ),
                                )
                            )
            except Exception as error:  # noqa: BLE001 — reclassified immediately below
                # Retrying after partial output would duplicate what the user
                # has already read, so only a failure before any output is
                # worth another attempt.
                if attempt == 2 or produced_output or not _is_retryable(error):
                    raise
                logger.warning("Gemini call failed before output; retrying once")
                time.sleep(self._retry_backoff_seconds)
                continue

            for call in tool_calls:
                yield call
            stop_reason = "tool_use" if tool_calls else _FINISH_REASON_MAP.get(
                finish_reason or "", "end_turn"
            )
            yield TurnEnd(stop_reason=stop_reason)
            return


def _to_tool(tools: Sequence[ToolSpec]) -> genai_types.Tool:
    return genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.input_schema,
            )
            for tool in tools
        ]
    )


def _to_contents(
    messages: Sequence[ConversationMessage],
) -> list[genai_types.Content]:
    contents: list[genai_types.Content] = []
    # Tracks which tool produced which call id, so a later ToolResultMessage
    # (which only carries the id) can fill in the name Gemini requires.
    tool_name_by_call_id: dict[str, str] = {}

    for message in messages:
        if isinstance(message, UserMessage):
            contents.append(
                genai_types.Content(role="user", parts=[genai_types.Part(text=message.text)])
            )
        elif isinstance(message, AssistantMessage):
            for call in message.tool_calls:
                tool_name_by_call_id[call.id] = call.name
            contents.append(
                genai_types.Content(role="model", parts=_assistant_parts(message))
            )
        else:
            _append_tool_result(contents, message, tool_name_by_call_id)

    return contents


def _assistant_parts(message: AssistantMessage) -> list[genai_types.Part]:
    parts: list[genai_types.Part] = []
    if message.text:
        parts.append(genai_types.Part(text=message.text))
    parts.extend(
        genai_types.Part(
            function_call=genai_types.FunctionCall(
                id=call.id, name=call.name, args=call.input
            ),
            # Required on replay or the API rejects the request with 400
            # "Function call is missing a thought_signature" — this is the
            # opaque value Gemini itself attached when it first emitted the
            # call, carried here via ToolCall.provider_data since the
            # signature lives on the Part, not inside the FunctionCall.
            thought_signature=(call.provider_data or {}).get("thought_signature"),
        )
        for call in message.tool_calls
    )
    return parts


def _append_tool_result(
    contents: list[genai_types.Content],
    message: ToolResultMessage,
    tool_name_by_call_id: dict[str, str],
) -> None:
    """All results of one parallel round belong in a single Content, mirroring
    how a real multi-function-call turn is answered."""
    part = genai_types.Part(
        function_response=genai_types.FunctionResponse(
            id=message.tool_call_id,
            name=tool_name_by_call_id.get(message.tool_call_id, message.tool_call_id),
            response=message.payload,
        )
    )

    last = contents[-1] if contents else None
    if (
        last is not None
        and last.role == "user"
        and last.parts
        and last.parts[0].function_response is not None
    ):
        last.parts.append(part)
        return

    contents.append(genai_types.Content(role="user", parts=[part]))
