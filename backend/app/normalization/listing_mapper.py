"""Composes the normalizers into one mapping: raw export record -> Listing.

This is the only place that knows the shape of the scraper's JSON; the rest
of the backend works with `Listing` alone.
"""

from __future__ import annotations

from typing import Any, Callable

from app.domain.listing import Listing
from app.normalization.features import (
    parse_area_type,
    parse_cellar,
    parse_furnished,
    parse_garden,
    parse_kitchen,
    parse_parking,
    parse_terraces,
)
from app.normalization.fields import parse_energy_class, parse_floor, parse_heating
from app.normalization.location import parse_location

# Raw `features` keys mapped onto a single typed field, by the function that
# converts the value. `posizione` and `garage` are handled separately: the
# first feeds three location fields, the second feeds two parking fields.
_SINGLE_VALUE_FEATURES: dict[str, tuple[str, Callable[[str], Any]]] = {
    "giardino": ("garden", parse_garden),
    "cantina": ("cellar", parse_cellar),
    "terrazzi": ("terraces", parse_terraces),
    "cucina": ("kitchen", parse_kitchen),
    "zona": ("area_type", parse_area_type),
    "arredato": ("furnished", parse_furnished),
}

_POSIZIONE_KEY = "posizione"
_GARAGE_KEY = "garage"


def to_listing(record: dict[str, Any]) -> Listing:
    features: dict[str, Any] = dict(record.get("features") or {})

    fields: dict[str, Any] = {
        "reference": record["reference"],
        "transaction": record["transaction"],
        "title": record["title"],
        "url": record["url"],
        "description": record.get("description"),
        "price_eur": record.get("price_eur"),
        "property_type": record.get("property_type"),
        "surface_sqm": record.get("surface_sqm"),
        "bedrooms": record.get("bedrooms"),
        "bathrooms": record.get("bathrooms"),
        "year_built": record.get("year_built"),
        "heating": parse_heating(record.get("heating")),
        "energy_class": parse_energy_class(record.get("energy_class")),
        "image_url": record.get("image_url"),
    }

    floor = parse_floor(record.get("floor"))
    fields["floor_label"] = floor.label
    fields["floor_level"] = floor.level

    posizione = features.pop(_POSIZIONE_KEY, None)
    location = parse_location(posizione) if posizione else None
    # The export leaves address/city/province empty and hides them inside
    # `posizione`, but a populated canonical field always wins.
    fields["address"] = record.get("address") or (location.address if location else None)
    fields["city"] = record.get("city") or (location.city if location else None)
    fields["province"] = record.get("province") or (location.province if location else None)

    garage = features.pop(_GARAGE_KEY, None)
    if garage is not None:
        fields["parking_spaces"], fields["parking_type"] = parse_parking(garage)

    for key, (field_name, parse) in _SINGLE_VALUE_FEATURES.items():
        value = features.pop(key, None)
        if value is not None:
            fields[field_name] = parse(value)

    # Whatever the source adds beyond the known keys survives untyped.
    fields["raw_features"] = {key: str(value) for key, value in features.items()}

    return Listing(**fields)
