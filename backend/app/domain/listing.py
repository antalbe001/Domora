"""Canonical `Listing` schema: the one contract the scraper writes and the
backend reads. Pure data — no I/O, no parsing of raw scraped strings (that
is `app.normalization`'s job)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

MIN_PLAUSIBLE_YEAR_BUILT = 500
MAX_PLAUSIBLE_YEAR_BUILT = 2035


class PropertyTransaction(str, Enum):
    SALE = "sale"
    RENT = "rent"


class EnergyClass(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class HeatingType(str, Enum):
    AUTONOMOUS = "autonomous"
    CENTRALIZED = "centralized"
    HEAT_METER = "heat_meter"
    NONE = "none"


class ParkingType(str, Enum):
    NONE = "none"
    OPEN = "open"
    COVERED = "covered"
    DOUBLE = "double"
    CONDOMINIAL = "condominial"


class KitchenType(str, Enum):
    SEPARATE = "separate"
    OPEN_SPACE = "open_space"
    KITCHENETTE = "kitchenette"


class AreaType(str, Enum):
    CENTRAL = "central"
    SEMI_CENTRAL = "semi_central"
    SUBURB = "suburb"


class FurnishedStatus(str, Enum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"


class Listing(BaseModel):
    reference: str
    transaction: PropertyTransaction
    title: str
    url: str
    description: str | None = None
    price_eur: int | None = None
    property_type: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    surface_sqm: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    floor_label: str | None = None
    floor_level: int | None = None
    year_built: int | None = None
    heating: HeatingType | None = None
    energy_class: EnergyClass | None = None
    image_url: str | None = None
    garden: bool | None = None
    cellar: bool | None = None
    terraces: int | None = None
    parking_spaces: int | None = None
    parking_type: ParkingType | None = None
    kitchen: KitchenType | None = None
    area_type: AreaType | None = None
    furnished: FurnishedStatus | None = None
    raw_features: dict[str, str] = Field(default_factory=dict)

    @field_validator("year_built")
    @classmethod
    def _year_built_must_be_plausible(cls, value: int | None) -> int | None:
        if value is not None and not (MIN_PLAUSIBLE_YEAR_BUILT <= value <= MAX_PLAUSIBLE_YEAR_BUILT):
            raise ValueError(
                f"year_built must be between {MIN_PLAUSIBLE_YEAR_BUILT} and "
                f"{MAX_PLAUSIBLE_YEAR_BUILT}, got {value}"
            )
        return value
