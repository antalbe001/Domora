from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from google.genai import errors as genai_errors

from app.llm.chat_model import (
    AssistantMessage,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    TurnEnd,
    UserMessage,
)
from app.llm.gemini_chat_model import GeminiChatModel
from app.llm.tools import SEARCH_LISTINGS


def _part(**kwargs: Any) -> SimpleNamespace:
    defaults = {"text": None, "function_call": None, "thought_signature": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _function_call(name: str, args: dict[str, Any], id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=id, name=name, args=args)


def _chunk(*parts: SimpleNamespace, finish_reason: str | None = None) -> SimpleNamespace:
    """A streamed GenerateContentResponse chunk, pared down to what the
    adapter reads: candidates[0].content.parts and .finish_reason."""
    content = SimpleNamespace(parts=list(parts))
    candidate = SimpleNamespace(content=content, finish_reason=finish_reason)
    return SimpleNamespace(candidates=[candidate])


class FakeModels:
    """Stands in for client.models, recording the request it was given."""

    def __init__(self, *turns: list[Any] | Exception) -> None:
        self._turns = list(turns)
        self.requests: list[dict[str, Any]] = []

    def generate_content_stream(self, **kwargs: Any) -> Iterator[Any]:
        self.requests.append(kwargs)
        turn = self._turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return iter(turn)


class FakeClient:
    def __init__(self, *turns: list[Any] | Exception) -> None:
        self.models = FakeModels(*turns)


def _model(client: FakeClient, **overrides: Any) -> GeminiChatModel:
    return GeminiChatModel(
        client=client,
        model="gemini-2.0-flash",
        retry_backoff_seconds=0,
        **overrides,
    )


def _server_error() -> genai_errors.ServerError:
    return genai_errors.ServerError(code=503, response_json={"error": {"message": "down"}})


def test_streams_the_text_of_a_turn_then_reports_its_end() -> None:
    client = FakeClient(
        [_chunk(_part(text="Ciao")), _chunk(_part(text="!"), finish_reason="STOP")]
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert events == [TextDelta("Ciao"), TextDelta("!"), TurnEnd(stop_reason="end_turn")]


def test_reports_a_tool_call_found_in_the_turn() -> None:
    client = FakeClient(
        [
            _chunk(_part(text="Cerco...")),
            _chunk(
                _part(
                    function_call=_function_call(
                        "search_listings", {"city": "Pordenone"}, id="call-xyz"
                    )
                ),
                finish_reason="STOP",
            ),
        ]
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="case")], []))

    assert events == [
        TextDelta("Cerco..."),
        ToolCall(id="call-xyz", name="search_listings", input={"city": "Pordenone"}),
        TurnEnd(stop_reason="tool_use"),
    ]


def test_generates_an_id_when_the_api_does_not_provide_one() -> None:
    """The plain (non-Enterprise) Gemini API may leave function_call.id unset;
    ChatService still needs a stable id to pair the result back."""
    client = FakeClient(
        [
            _chunk(
                _part(function_call=_function_call("search_listings", {})),
                _part(function_call=_function_call("get_listing_detail", {"reference": "V1"})),
                finish_reason="STOP",
            )
        ]
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="case")], []))

    tool_calls = [event for event in events if isinstance(event, ToolCall)]
    assert [call.id for call in tool_calls] == ["call-1", "call-2"]
    assert len({call.id for call in tool_calls}) == 2


def test_captures_and_replays_the_thought_signature_gemini_requires() -> None:
    """Confirmed against the live API: a function_call part replayed without
    its original thought_signature is rejected with a 400 — Gemini's
    equivalent of Anthropic's "preserved thinking". The signature sits on
    the Part, not inside the FunctionCall."""
    client = FakeClient([_chunk(finish_reason="STOP")])
    tool_call = ToolCall(
        id="call-1",
        name="search_listings",
        input={"city": "Pordenone"},
        provider_data={"thought_signature": b"opaque-signature"},
    )
    conversation = [
        UserMessage(text="case a Pordenone"),
        AssistantMessage(tool_calls=[tool_call]),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 1}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    assistant_part = client.models.requests[0]["contents"][1].parts[0]
    assert assistant_part.thought_signature == b"opaque-signature"


def test_captures_the_thought_signature_from_a_streamed_tool_call() -> None:
    client = FakeClient(
        [
            _chunk(
                _part(
                    function_call=_function_call("search_listings", {}),
                    thought_signature=b"opaque-signature",
                ),
                finish_reason="STOP",
            )
        ]
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="case")], []))

    tool_call = next(event for event in events if isinstance(event, ToolCall))
    assert tool_call.provider_data == {"thought_signature": b"opaque-signature"}


def test_sends_the_system_instruction_model_and_tools() -> None:
    client = FakeClient([_chunk(finish_reason="STOP")])

    list(_model(client).stream("sistema", [UserMessage(text="ciao")], [SEARCH_LISTINGS]))

    request = client.models.requests[0]
    assert request["model"] == "gemini-2.0-flash"
    config = request["config"]
    assert config.system_instruction == "sistema"
    declarations = config.tools[0].function_declarations
    assert declarations[0].name == SEARCH_LISTINGS.name
    assert declarations[0].description == SEARCH_LISTINGS.description
    assert declarations[0].parameters_json_schema == SEARCH_LISTINGS.input_schema


def test_translates_user_and_assistant_turns() -> None:
    client = FakeClient([_chunk(finish_reason="STOP")])
    conversation = [
        UserMessage(text="case a Pordenone"),
        AssistantMessage(
            text="Cerco...",
            tool_calls=[ToolCall(id="call-1", name="search_listings", input={"city": "Pordenone"})],
        ),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 1}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    contents = client.models.requests[0]["contents"]
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "case a Pordenone"

    assert contents[1].role == "model"
    assert contents[1].parts[0].text == "Cerco..."
    assert contents[1].parts[1].function_call.name == "search_listings"
    assert contents[1].parts[1].function_call.args == {"city": "Pordenone"}

    assert contents[2].role == "user"
    response_part = contents[2].parts[0].function_response
    assert response_part.name == "search_listings"
    assert response_part.response == {"total": 1}


def test_parallel_tool_results_travel_in_a_single_content() -> None:
    client = FakeClient([_chunk(finish_reason="STOP")])
    conversation = [
        UserMessage(text="due ricerche"),
        AssistantMessage(
            tool_calls=[
                ToolCall(id="call-1", name="search_listings", input={}),
                ToolCall(id="call-2", name="get_listing_detail", input={"reference": "V1"}),
            ]
        ),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 1}),
        ToolResultMessage(tool_call_id="call-2", payload={"listing": {"reference": "V1"}}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    contents = client.models.requests[0]["contents"]
    assert len(contents) == 3
    names = [part.function_response.name for part in contents[2].parts]
    assert names == ["search_listings", "get_listing_detail"]


def test_an_assistant_turn_with_no_text_sends_only_its_tool_call() -> None:
    client = FakeClient([_chunk(finish_reason="STOP")])
    conversation = [
        UserMessage(text="case"),
        AssistantMessage(tool_calls=[ToolCall(id="call-1", name="search_listings", input={})]),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 0}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    parts = client.models.requests[0]["contents"][1].parts
    assert len(parts) == 1
    assert parts[0].function_call is not None


def test_retries_once_when_the_turn_fails_before_producing_anything() -> None:
    client = FakeClient(_server_error(), [_chunk(_part(text="Ciao")), _chunk(finish_reason="STOP")])

    events = list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert events == [TextDelta("Ciao"), TurnEnd(stop_reason="end_turn")]
    assert len(client.models.requests) == 2


def test_gives_up_after_the_retry() -> None:
    client = FakeClient(_server_error(), _server_error())

    with pytest.raises(genai_errors.ServerError):
        list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert len(client.models.requests) == 2
