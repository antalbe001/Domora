"""The search contract shared by the LLM tool, the service layer and the
repositories: every field is optional, and `None` means "don't filter on
this". Pure data — how the criteria are applied is each repository's
business.

The field descriptions are what the model reads when it fills the
`search_listings` tool in, so they are written for that audience.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.listing import (
    AreaType,
    EnergyClass,
    FurnishedStatus,
    PropertyTransaction,
)


class SearchCriteria(BaseModel):
    transaction: PropertyTransaction | None = Field(
        default=None,
        description="Whether the listing is for sale or for rent.",
    )
    city: str | None = Field(
        default=None,
        description=(
            "Comune the property is in, e.g. 'Pordenone', 'Sacile'. "
            "Matched case-insensitively."
        ),
    )
    province: str | None = Field(
        default=None,
        description="Two-letter Italian province code, e.g. 'PN' for Pordenone.",
    )
    property_type: str | None = Field(
        default=None,
        description=(
            "Italian property type as the agency writes it: 'Appartamento', "
            "'Villa Casa indipendente', 'Terreno', 'Capannone', 'Bifamiliare', "
            "'Rustico o Casale', 'Negozio', 'Casa in linea', 'Ufficio', "
            "'Loft o Openspace'."
        ),
    )
    price_min: int | None = Field(
        default=None,
        description="Lowest acceptable price in euros (monthly rent for rentals).",
    )
    price_max: int | None = Field(
        default=None,
        description="Highest acceptable price in euros (monthly rent for rentals).",
    )
    surface_min: int | None = Field(
        default=None, description="Smallest acceptable floor area in square metres."
    )
    bedrooms_min: int | None = Field(
        default=None, description="Fewest acceptable bedrooms."
    )
    bathrooms_min: int | None = Field(
        default=None, description="Fewest acceptable bathrooms."
    )
    floor_level_min: int | None = Field(
        default=None,
        description=(
            "Lowest acceptable floor, as a number: 0 is ground floor, 1 is "
            "first floor. Use it for requests like 'not on the ground floor'."
        ),
    )
    terraces_min: int | None = Field(
        default=None, description="Fewest acceptable terraces."
    )
    energy_class: EnergyClass | None = Field(
        default=None,
        description=(
            "Exact energy-efficiency class. Only about half the catalogue has "
            "one, and a listing without it never matches this filter."
        ),
    )
    area_type: AreaType | None = Field(
        default=None,
        description="Where in town the property sits: central, semi-central or suburban.",
    )
    furnished: FurnishedStatus | None = Field(
        default=None, description="Whether the property comes furnished."
    )
    garden: bool | None = Field(
        default=None, description="True to require a garden, false to require none."
    )
    cellar: bool | None = Field(
        default=None, description="True to require a cellar, false to require none."
    )
    has_parking: bool | None = Field(
        default=None,
        description=(
            "True to require somewhere to park — a garage or a parking space "
            "of any kind."
        ),
    )
    keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Free-text words for qualities no other field captures, e.g. "
            "'ristrutturato', 'luminoso', 'ascensore'. Matched against the "
            "listing's title, description and untyped features; every word "
            "must appear, so keep the list short. Do not put here anything a "
            "structured field above can express."
        ),
    )
