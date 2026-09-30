"""The search contract shared by the LLM tool, the service layer and the
repositories: every field is optional, and `None` means "don't filter on
this". Pure data — how the criteria are applied is each repository's
business."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.listing import (
    AreaType,
    EnergyClass,
    FurnishedStatus,
    PropertyTransaction,
)


class SearchCriteria(BaseModel):
    transaction: PropertyTransaction | None = None
    city: str | None = None
    province: str | None = None
    property_type: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    surface_min: int | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    floor_level_min: int | None = None
    terraces_min: int | None = None
    energy_class: EnergyClass | None = None
    area_type: AreaType | None = None
    furnished: FurnishedStatus | None = None
    garden: bool | None = None
    cellar: bool | None = None
    has_parking: bool | None = None
    # Free-text fallback for qualities no structured field captures
    # ("ristrutturato", "luminoso"); all of them must be present.
    keywords: list[str] = Field(default_factory=list)
