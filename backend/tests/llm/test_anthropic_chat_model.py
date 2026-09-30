from types import SimpleNamespace
from typing import Any, Iterator

import anthropic
import httpx
import pytest

from app.llm.anthropic_chat_model import AnthropicChatModel
from app.llm.chat_model import (
    AssistantMessage,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    TurnEnd,
    UserMessage,
)
from app.llm.tools import SEARCH_LISTINGS


def _text_delta(text: str) -> SimpleNamespace:
    """A content_block_delta event as the SDK emits it."""
    return SimpleNamespace(
        type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=text)
    )


def _final_message(*, stop_reason: str = "end_turn", content: list[Any] | None = None) -> Any:
    return SimpleNamespace(stop_reason=stop_reason, content=content or [])


def _tool_use_block(id: str, name: str, tool_input: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id, name=name, input=tool_input)


class _FakeStream:
    def __init__(self, events: list[Any], final: Any) -> None:
        self._events = events
        self._final = final

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def __iter__(self) -> Iterator[Any]:
        return iter(self._events)

    def get_final_message(self) -> Any:
        return self._final


class FakeAnthropic:
    """Stands in for anthropic.Anthropic, recording the request it was given."""

    def __init__(self, *turns: tuple[list[Any], Any] | Exception) -> None:
        self._turns = list(turns)
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kwargs: Any) -> _FakeStream:
        self.requests.append(kwargs)
        turn = self._turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        events, final = turn
        return _FakeStream(events, final)


def _model(client: FakeAnthropic, **overrides: Any) -> AnthropicChatModel:
    return AnthropicChatModel(
        client=client,
        model="claude-haiku-4-5",
        retry_backoff_seconds=0,
        **overrides,
    )


def _connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )


def test_streams_the_text_of_a_turn_then_reports_its_end() -> None:
    client = FakeAnthropic(([_text_delta("Ciao"), _text_delta("!")], _final_message()))

    events = list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert events == [TextDelta("Ciao"), TextDelta("!"), TurnEnd(stop_reason="end_turn")]


def test_reports_the_tool_calls_of_the_finished_turn() -> None:
    client = FakeAnthropic(
        (
            [_text_delta("Cerco...")],
            _final_message(
                stop_reason="tool_use",
                content=[_tool_use_block("call-1", "search_listings", {"city": "Pordenone"})],
            ),
        )
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="case")], []))

    assert events == [
        TextDelta("Cerco..."),
        ToolCall(id="call-1", name="search_listings", input={"city": "Pordenone"}),
        TurnEnd(stop_reason="tool_use"),
    ]


def test_sends_the_system_prompt_model_and_tools() -> None:
    client = FakeAnthropic(([], _final_message()))

    list(_model(client).stream("sistema", [UserMessage(text="ciao")], [SEARCH_LISTINGS]))

    request = client.requests[0]
    assert request["model"] == "claude-haiku-4-5"
    assert request["system"] == "sistema"
    assert request["tools"] == [
        {
            "name": SEARCH_LISTINGS.name,
            "description": SEARCH_LISTINGS.description,
            "input_schema": SEARCH_LISTINGS.input_schema,
        }
    ]


def test_translates_an_assistant_turn_with_its_tool_calls() -> None:
    client = FakeAnthropic(([], _final_message()))
    conversation = [
        UserMessage(text="case a Pordenone"),
        AssistantMessage(
            text="Cerco...",
            tool_calls=[ToolCall(id="call-1", name="search_listings", input={"city": "Pordenone"})],
        ),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 1}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    messages = client.requests[0]["messages"]
    assert messages[0] == {"role": "user", "content": "case a Pordenone"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == [
        {"type": "text", "text": "Cerco..."},
        {
            "type": "tool_use",
            "id": "call-1",
            "name": "search_listings",
            "input": {"city": "Pordenone"},
        },
    ]
    assert messages[2]["role"] == "user"
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[2]["content"][0]["tool_use_id"] == "call-1"


def test_parallel_tool_results_travel_in_a_single_user_message() -> None:
    """Splitting them across messages teaches the model to stop calling tools
    in parallel."""
    client = FakeAnthropic(([], _final_message()))
    conversation = [
        UserMessage(text="due ricerche"),
        AssistantMessage(
            tool_calls=[
                ToolCall(id="call-1", name="search_listings", input={}),
                ToolCall(id="call-2", name="search_listings", input={}),
            ]
        ),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 1}),
        ToolResultMessage(tool_call_id="call-2", payload={"total": 2}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    messages = client.requests[0]["messages"]
    assert len(messages) == 3
    assert [block["tool_use_id"] for block in messages[2]["content"]] == ["call-1", "call-2"]


def test_an_assistant_turn_with_no_text_sends_only_its_tool_calls() -> None:
    client = FakeAnthropic(([], _final_message()))
    conversation = [
        UserMessage(text="case"),
        AssistantMessage(tool_calls=[ToolCall(id="call-1", name="search_listings", input={})]),
        ToolResultMessage(tool_call_id="call-1", payload={"total": 0}),
    ]

    list(_model(client).stream("sistema", conversation, []))

    assert [block["type"] for block in client.requests[0]["messages"][1]["content"]] == [
        "tool_use"
    ]


def test_retries_once_when_the_turn_fails_before_producing_anything() -> None:
    client = FakeAnthropic(
        _connection_error(),
        ([_text_delta("Ciao")], _final_message()),
    )

    events = list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert events == [TextDelta("Ciao"), TurnEnd(stop_reason="end_turn")]
    assert len(client.requests) == 2


def test_gives_up_after_the_retry() -> None:
    client = FakeAnthropic(_connection_error(), _connection_error())

    with pytest.raises(anthropic.APIConnectionError):
        list(_model(client).stream("sistema", [UserMessage(text="ciao")], []))

    assert len(client.requests) == 2
