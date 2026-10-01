import pytest

from app.dependencies import _build_chat_model
from app.llm.anthropic_chat_model import AnthropicChatModel
from app.llm.gemini_chat_model import GeminiChatModel
from app.settings import Settings


def test_builds_the_anthropic_adapter_when_selected() -> None:
    settings = Settings(llm_provider="anthropic", anthropic_api_key="sk-ant-test")

    assert isinstance(_build_chat_model(settings), AnthropicChatModel)


def test_builds_the_gemini_adapter_when_selected() -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="test")

    assert isinstance(_build_chat_model(settings), GeminiChatModel)


def test_rejects_an_unsupported_provider_instead_of_silently_picking_one() -> None:
    settings = Settings.model_construct(llm_provider="mistral")  # bypass the Literal

    with pytest.raises(ValueError, match="mistral"):
        _build_chat_model(settings)
