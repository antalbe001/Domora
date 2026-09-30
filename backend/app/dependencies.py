"""Composition root: builds the object graph once and hands the pieces to the
routers through FastAPI's `Depends`. No DI container — at this size the
wiring is easier to read as plain code."""

from __future__ import annotations

import logging
from functools import lru_cache

import anthropic

from app.llm.anthropic_chat_model import AnthropicChatModel
from app.llm.listing_tools import ListingTools
from app.llm.prompts import SYSTEM_PROMPT
from app.repositories.export_loader import load_listings
from app.repositories.in_memory import InMemoryListingRepository
from app.services.chat_service import ChatService
from app.services.conversation_store import InMemoryConversationStore
from app.services.rate_limiter import InMemoryRateLimiter
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_listing_repository() -> InMemoryListingRepository:
    """The catalogue, loaded once at startup and replaceable via
    /admin/reload."""
    settings = get_settings()
    try:
        listings = load_listings(settings.listings_path)
    except OSError as error:
        # An empty catalogue still serves: the chatbot will honestly report
        # finding nothing, which beats refusing to boot.
        logger.error("Could not read %s: %s", settings.listings_path, error)
        listings = []

    logger.info("Loaded %d listings from %s", len(listings), settings.listings_path)
    return InMemoryListingRepository(listings)


@lru_cache
def get_conversation_store() -> InMemoryConversationStore:
    settings = get_settings()
    return InMemoryConversationStore(
        ttl_minutes=settings.session_ttl_minutes,
        max_turns=settings.session_max_turns,
    )


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    settings = get_settings()
    return InMemoryRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        per_seconds=settings.rate_limit_per_seconds,
    )


@lru_cache
def get_chat_service() -> ChatService:
    settings: Settings = get_settings()
    return ChatService(
        model=AnthropicChatModel(
            client=anthropic.Anthropic(api_key=settings.anthropic_api_key),
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
        ),
        tools=ListingTools(
            repository=get_listing_repository(), max_results=settings.max_results
        ),
        store=get_conversation_store(),
        system_prompt=SYSTEM_PROMPT,
    )
