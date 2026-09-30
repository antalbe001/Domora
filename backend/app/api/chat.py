"""The chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest
from app.api.sse import to_sse
from app.dependencies import get_chat_service, get_rate_limiter
from app.services.chat_service import ChatService
from app.services.rate_limiter import RateLimiter

router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> StreamingResponse:
    if not rate_limiter.allow(request.session_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Troppe richieste. Attendi qualche istante e riprova.",
        )

    return StreamingResponse(
        to_sse(service.answer(request.session_id, request.message)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
