"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, chat
from app.dependencies import get_listing_repository
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Surfaces a missing or broken export in the logs at boot rather than on
    # the first visitor's question.
    get_listing_repository()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Chatbot annunci immobiliari", version="0.1.0", lifespan=_lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    return app


app = create_app()
