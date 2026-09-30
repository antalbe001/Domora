from typing import Any

from app.domain.listing import (
    AreaType,
    EnergyClass,
    KitchenType,
    ParkingType,
    PropertyTransaction,
)
from app.normalization.listing_mapper import to_listing


def _raw_record(**overrides: Any) -> dict[str, Any]:
    """A record shaped exactly like one entry of the scraper's annunci.json."""
    record: dict[str, Any] = {
        "reference": "120314",
        "transaction": "rent",
        "title": "120314 – Bicamere zona Villanova",
        "url": "https://salamonimmobiliare.com/annunci/120314-bicamere-zona-villanova/",
        "description": "Appartamento al secondo piano con ascensore.",
        "price_eur": 500,
        "property_type": "Appartamento",
        "address": None,
        "city": None,
        "province": None,
        "surface_sqm": 83,
        "bedrooms": 2,
        "bathrooms": 2,
        "floor": 2,
        "year_built": 1980,
        "heating": None,
        "energy_class": "B",
        "features": {
            "posizione": "Via Carlo Goldoni 16 - PORDENONE",
            "cucina": "Cucina separata",
            "terrazzi": "1",
            "garage": "0",
            "giardino": "No",
            "cantina": "No",
            "zona": "Centrale",
            "arredato": "Parzialmente",
        },
    }
    record.update(overrides)
    return record


def test_maps_a_raw_export_record_onto_the_canonical_listing() -> None:
    listing = to_listing(_raw_record())

    assert listing.reference == "120314"
    assert listing.transaction is PropertyTransaction.RENT
    assert listing.price_eur == 500
    assert listing.surface_sqm == 83
    assert listing.energy_class is EnergyClass.B
    assert listing.heating is None


def test_fills_the_empty_location_fields_from_the_raw_posizione() -> None:
    listing = to_listing(_raw_record())

    assert listing.address == "Via Carlo Goldoni 16"
    assert listing.city == "Pordenone"
    assert listing.province == "PN"


def test_maps_the_raw_features_onto_typed_fields() -> None:
    listing = to_listing(_raw_record())

    assert listing.kitchen is KitchenType.SEPARATE
    assert listing.terraces == 1
    assert listing.parking_spaces == 0
    assert listing.parking_type is ParkingType.NONE
    assert listing.garden is False
    assert listing.cellar is False
    assert listing.area_type is AreaType.CENTRAL


def test_derives_the_floor_label_and_level() -> None:
    listing = to_listing(_raw_record(floor="terra"))

    assert listing.floor_label == "terra"
    assert listing.floor_level == 0


def test_keeps_unknown_feature_keys_untyped_and_drops_the_consumed_ones() -> None:
    listing = to_listing(
        _raw_record(
            features={
                "posizione": "Via Carlo Goldoni 16 - PORDENONE",
                "giardino": "Si",
                "ascensore": "Si",
                "superficie_terrazzo": "30 mq",
            }
        )
    )

    assert listing.garden is True
    assert listing.raw_features == {"ascensore": "Si", "superficie_terrazzo": "30 mq"}


def test_leaves_fields_unknown_when_their_feature_key_is_absent() -> None:
    listing = to_listing(
        _raw_record(features={"posizione": "Via Carlo Goldoni 16 - PORDENONE"})
    )

    assert listing.garden is None
    assert listing.cellar is None
    assert listing.terraces is None
    assert listing.kitchen is None
    assert listing.area_type is None
    assert listing.furnished is None
    assert listing.parking_spaces is None
    assert listing.parking_type is None


def test_maps_a_record_with_no_location_information_at_all() -> None:
    listing = to_listing(_raw_record(features={}))

    assert listing.address is None
    assert listing.city is None
    assert listing.province is None
