"""Normalizes the top-level scalar fields of the scraper export that are
not plain pass-throughs: heating, energy_class and floor.

Separate from `features.py`, which covers the keys of the raw `features`
dict, and from `location.py`, which covers `features["posizione"]`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.listing import EnergyClass, HeatingType

_HEATING_TYPES: dict[str, HeatingType] = {
    "Autonomo": HeatingType.AUTONOMOUS,
    "Centralizzato": HeatingType.CENTRALIZED,
    "Contacalorie": HeatingType.HEAT_METER,
    "No riscaldamento": HeatingType.NONE,
}

# Not a class: the agency uses it while the certificate is being drafted,
# so it carries no information and must not survive normalization.
ENERGY_CLASS_PLACEHOLDER = "In fase di redazione"


def parse_heating(value: str | None) -> HeatingType | None:
    if value is None:
        return None
    return _HEATING_TYPES[value]


def parse_energy_class(value: str | None) -> EnergyClass | None:
    if value is None or value == ENERGY_CLASS_PLACEHOLDER:
        return None
    return EnergyClass(value)


# Named floors the source uses instead of a number, with the level they sit
# at for sorting and "at least floor N" filtering.
_NAMED_FLOOR_LEVELS: dict[str, int] = {
    "terra": 0,
    "rialzato": 0,
}


@dataclass(frozen=True)
class ParsedFloor:
    label: str | None
    level: int | None


def parse_floor(value: int | str | None) -> ParsedFloor:
    """`floor` arrives either as a number or as a phrase ("terra",
    "rialzato", "5 oltre"). The phrase is kept verbatim for display and
    reduced to a number for filtering."""
    if value is None:
        return ParsedFloor(label=None, level=None)

    if isinstance(value, int):
        return ParsedFloor(label=str(value), level=value)

    label = value.strip()
    if label in _NAMED_FLOOR_LEVELS:
        return ParsedFloor(label=label, level=_NAMED_FLOOR_LEVELS[label])

    leading_number = re.match(r"\d+", label)
    return ParsedFloor(
        label=label,
        level=int(leading_number.group(0)) if leading_number else None,
    )
