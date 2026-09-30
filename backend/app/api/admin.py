"""Operational endpoints: reloading the catalogue, and health."""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.schemas import HealthResponse, ReloadResponse
from app.dependencies import get_listing_repository
from app.domain.search import SearchCriteria
from app.repositories.export_loader import load_listings
from app.repositories.in_memory import InMemoryListingRepository
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


def _require_admin(authorization: str | None, settings: Settings) -> None:
    if not settings.admin_token:
        # An unset token closes the endpoint; it never means "open to all".
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reload endpoint is disabled: no admin token configured.",
        )

    presented = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(presented, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token."
        )


@router.post("/admin/reload", response_model=ReloadResponse)
def reload_listings(
    authorization: str | None = Header(default=None),
    repository: InMemoryListingRepository = Depends(get_listing_repository),
    settings: Settings = Depends(get_settings),
) -> ReloadResponse:
    _require_admin(authorization, settings)

    try:
        listings = load_listings(settings.listings_path)
    except OSError as error:
        logger.error("Reload failed reading %s: %s", settings.listings_path, error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not read {settings.listings_path}.",
        ) from error

    repository.replace(listings)
    logger.info("Reloaded %d listings from %s", len(listings), settings.listings_path)
    return ReloadResponse(loaded=len(listings))


@router.get("/health", response_model=HealthResponse)
def health(
    repository: InMemoryListingRepository = Depends(get_listing_repository),
) -> HealthResponse:
    return HealthResponse(
        status="ok", listings=len(repository.search(SearchCriteria()))
    )
