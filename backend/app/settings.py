"""Configuration, read from the environment and `.env` (never committed)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm.anthropic_chat_model import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from app.llm.listing_tools import DEFAULT_MAX_RESULTS
from app.services.conversation_store import DEFAULT_MAX_TURNS, DEFAULT_TTL_MINUTES
from app.services.rate_limiter import DEFAULT_MAX_REQUESTS, DEFAULT_PER_SECONDS

MAX_MESSAGE_LENGTH = 500


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: str = ""
    anthropic_model: str = DEFAULT_MODEL
    anthropic_max_tokens: int = DEFAULT_MAX_TOKENS

    # Where the scraper leaves its export, relative to the backend directory.
    listings_path: Path = Path("../annunci.json")

    # Guards the reload endpoint. Empty means the endpoint is closed.
    admin_token: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    max_results: int = DEFAULT_MAX_RESULTS
    session_ttl_minutes: int = DEFAULT_TTL_MINUTES
    session_max_turns: int = DEFAULT_MAX_TURNS
    rate_limit_max_requests: int = DEFAULT_MAX_REQUESTS
    rate_limit_per_seconds: int = DEFAULT_PER_SECONDS


@lru_cache
def get_settings() -> Settings:
    return Settings()
