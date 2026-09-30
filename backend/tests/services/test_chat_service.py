from typing import Any, Iterator, Sequence

from app.domain.listing import Listing, PropertyTransaction
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
from app.llm.listing_tools import ListingTools
from app.llm.tools import ToolSpec
from app.repositories.in_memory import InMemoryListingRepository
from app.services.chat_service import ChatService, Listings, TextChunk
from app.services.conversation_store import InMemoryConversationStore, Role

SYSTEM_PROMPT = "Sei l'assistente di un'agenzia immobiliare."


class ScriptedChatModel:
    """A ChatModel that replays prepared turns and records what it was asked."""

    def __init__(self, *turns: list[ModelEvent]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    def stream(
        self,
        system: str,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolSpec],
    ) -> Iterator[ModelEvent]:
        self.calls.append({"system": system, "messages": list(messages), "tools": list(tools)})
        if not self._turns:
            raise AssertionError("the model was called more times than the script allows")
        yield from self._turns.pop(0)


def _listing(reference: str, **overrides: Any) -> Listing:
    fields: dict[str, Any] = {
        "reference": reference,
        "transaction": PropertyTransaction.SALE,
        "title": f"{reference} – Appartamento",
        "url": f"https://example.test/annunci/{reference.lower()}/",
        "price_eur": 120_000,
        "city": "Pordenone",
    }
    fields.update(overrides)
    return Listing(**fields)


def _service(
    model: ScriptedChatModel,
    *listings: Listing,
    store: InMemoryConversationStore | None = None,
    max_tool_rounds: int = 4,
) -> ChatService:
    return ChatService(
        model=model,
        tools=ListingTools(repository=InMemoryListingRepository(list(listings))),
        store=store or InMemoryConversationStore(),
        system_prompt=SYSTEM_PROMPT,
        max_tool_rounds=max_tool_rounds,
    )


def _text_of(events: list[Any]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextChunk))


def _search_call(**criteria: Any) -> list[ModelEvent]:
    return [
        ToolCall(id="call-1", name="search_listings", input=criteria),
        TurnEnd(stop_reason="tool_use"),
    ]


def test_streams_a_plain_answer_that_needs_no_tool() -> None:
    model = ScriptedChatModel(
        [TextDelta("Posso "), TextDelta("aiutarti."), TurnEnd(stop_reason="end_turn")]
    )
    service = _service(model)

    events = list(service.answer("s1", "ciao"))

    assert _text_of(events) == "Posso aiutarti."


def test_runs_the_requested_search_and_streams_the_answer_after_it() -> None:
    model = ScriptedChatModel(
        _search_call(city="Pordenone"),
        [TextDelta("Ne ho trovato 1."), TurnEnd(stop_reason="end_turn")],
    )
    service = _service(model, _listing("V1"))

    events = list(service.answer("s1", "case a Pordenone"))

    assert _text_of(events) == "Ne ho trovato 1."
    listings_events = [event for event in events if isinstance(event, Listings)]
    assert [listing.reference for listing in listings_events[0].listings] == ["V1"]


def test_the_model_sees_the_tool_result_on_its_next_turn() -> None:
    model = ScriptedChatModel(
        _search_call(city="Pordenone"),
        [TextDelta("fatto"), TurnEnd(stop_reason="end_turn")],
    )
    service = _service(model, _listing("V1"))

    list(service.answer("s1", "case a Pordenone"))

    second_turn_messages = model.calls[1]["messages"]
    tool_results = [
        message for message in second_turn_messages if isinstance(message, ToolResultMessage)
    ]
    assert tool_results[0].payload["total"] == 1
    assert tool_results[0].tool_call_id == "call-1"


def test_text_written_before_the_tool_call_still_reaches_the_user() -> None:
    model = ScriptedChatModel(
        [
            TextDelta("Cerco a Pordenone..."),
            ToolCall(id="call-1", name="search_listings", input={"city": "Pordenone"}),
            TurnEnd(stop_reason="tool_use"),
        ],
        [TextDelta(" Ne ho trovato 1."), TurnEnd(stop_reason="end_turn")],
    )
    service = _service(model, _listing("V1"))

    events = list(service.answer("s1", "case a Pordenone"))

    assert _text_of(events) == "Cerco a Pordenone... Ne ho trovato 1."


def test_remembers_the_exchange_for_the_next_question() -> None:
    store = InMemoryConversationStore()
    model = ScriptedChatModel(
        [TextDelta("Ne ho 7."), TurnEnd(stop_reason="end_turn")],
        [TextDelta("Di questi, 2."), TurnEnd(stop_reason="end_turn")],
    )
    service = _service(model, store=store)

    list(service.answer("s1", "trilocali a Pordenone"))
    list(service.answer("s1", "e con due bagni?"))

    assert [(turn.role, turn.text) for turn in store.history("s1")] == [
        (Role.USER, "trilocali a Pordenone"),
        (Role.ASSISTANT, "Ne ho 7."),
        (Role.USER, "e con due bagni?"),
        (Role.ASSISTANT, "Di questi, 2."),
    ]
    replayed = model.calls[1]["messages"]
    assert [message.text for message in replayed if isinstance(message, UserMessage)] == [
        "trilocali a Pordenone",
        "e con due bagni?",
    ]
    assert [
        message.text for message in replayed if isinstance(message, AssistantMessage)
    ] == ["Ne ho 7."]


def test_passes_the_system_prompt_and_the_tools_to_the_model() -> None:
    model = ScriptedChatModel([TextDelta("ok"), TurnEnd(stop_reason="end_turn")])

    list(_service(model).answer("s1", "ciao"))

    assert model.calls[0]["system"] == SYSTEM_PROMPT
    assert {tool.name for tool in model.calls[0]["tools"]} == {
        "search_listings",
        "get_listing_detail",
    }


def test_an_empty_result_set_is_handed_to_the_model_as_it_is() -> None:
    model = ScriptedChatModel(
        _search_call(city="Sacile"),
        [TextDelta("Nessun risultato."), TurnEnd(stop_reason="end_turn")],
    )
    service = _service(model, _listing("V1", city="Pordenone"))

    events = list(service.answer("s1", "case a Sacile"))

    assert _text_of(events) == "Nessun risultato."
    assert [event for event in events if isinstance(event, Listings)] == []


def test_stops_calling_tools_once_the_round_limit_is_reached() -> None:
    model = ScriptedChatModel(*[_search_call(city="Pordenone") for _ in range(5)])
    service = _service(model, _listing("V1"), max_tool_rounds=2)

    list(service.answer("s1", "case a Pordenone"))

    assert len(model.calls) == 2
