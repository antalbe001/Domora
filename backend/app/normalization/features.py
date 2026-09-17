"""Maps the raw string values found under `features` in the scraper export
(8 known keys: posizione — handled by `location.py` — giardino, terrazzi,
garage, cantina, cucina, zona, arredato) to the typed `Listing` fields.

One pure function per raw key: each is its own seam, not an internal
of a single "normalize everything" call.
"""

from __future__ import annotations

from app.domain.listing import AreaType, FurnishedStatus, KitchenType, ParkingType

_TEXTUAL_PARKING_TYPES: dict[str, tuple[int, ParkingType]] = {
    "Posto auto scoperto": (1, ParkingType.OPEN),
    "Posto auto coperto": (1, ParkingType.COVERED),
    "Doppio": (2, ParkingType.DOUBLE),
    "Posto auto condominiale": (1, ParkingType.CONDOMINIAL),
}

_KITCHEN_TYPES: dict[str, KitchenType] = {
    "Cucina separata": KitchenType.SEPARATE,
    "Open space": KitchenType.OPEN_SPACE,
    "Angolo cottura": KitchenType.KITCHENETTE,
}

_AREA_TYPES: dict[str, AreaType] = {
    "Centrale": AreaType.CENTRAL,
    "Periferia": AreaType.SUBURB,
    "Semicentrale": AreaType.SEMI_CENTRAL,
}

_FURNISHED_STATUSES: dict[str, FurnishedStatus] = {
    "Si": FurnishedStatus.YES,
    "No": FurnishedStatus.NO,
    "Parzialmente": FurnishedStatus.PARTIAL,
}


def _parse_si_no(value: str) -> bool:
    return value == "Si"


def parse_garden(value: str) -> bool:
    return _parse_si_no(value)


def parse_cellar(value: str) -> bool:
    return _parse_si_no(value)


def parse_terraces(value: str) -> int:
    return int(value)


def parse_parking(value: str) -> tuple[int, ParkingType]:
    """"garage" mixes bare counts ("0","1","2" — a numbered garage box,
    hence COVERED) with textual descriptions of the parking type."""
    if value in _TEXTUAL_PARKING_TYPES:
        return _TEXTUAL_PARKING_TYPES[value]

    spaces = int(value)
    return (spaces, ParkingType.NONE if spaces == 0 else ParkingType.COVERED)


def parse_kitchen(value: str) -> KitchenType:
    return _KITCHEN_TYPES[value]


def parse_area_type(value: str) -> AreaType:
    return _AREA_TYPES[value]


def parse_furnished(value: str) -> FurnishedStatus:
    return _FURNISHED_STATUSES[value]
