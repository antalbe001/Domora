"""Request/response shapes of the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.settings import MAX_MESSAGE_LENGTH


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    # Capped to keep one turn's cost and abuse surface bounded.
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ReloadResponse(BaseModel):
    loaded: int


class HealthResponse(BaseModel):
    status: str
    listings: int
