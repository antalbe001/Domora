import pytest
from pydantic import ValidationError

from app.domain.listing import (
    AreaType,
    EnergyClass,
    FurnishedStatus,
    HeatingType,
    KitchenType,
    Listing,
    ParkingType,
    PropertyTransaction,
)


def _valid_listing_kwargs(**overrides: object) -> dict:
    kwargs = dict(
        reference="V2645",
        transaction=PropertyTransaction.SALE,
        title="V2645 – Appartamento con terrazzo",
        url="https://salamonimmobiliare.com/annunci/v2645-esempio/",
        description="Un appartamento luminoso.",
        price_eur=175_000,
        property_type="Appartamento",
        address="Via Carlo Goldoni 16",
        city="Pordenone",
        province="PN",
        surface_sqm=90,
        bedrooms=2,
        bathrooms=1,
        floor_label="2",
        floor_level=2,
        year_built=1980,
        heating=HeatingType.AUTONOMOUS,
        energy_class=EnergyClass.B,
        image_url="https://salamonimmobiliare.com/img/v2645-cover.jpg",
        garden=False,
        cellar=True,
        terraces=1,
        parking_spaces=1,
        parking_type=ParkingType.COVERED,
        kitchen=KitchenType.SEPARATE,
        area_type=AreaType.CENTRAL,
        furnished=FurnishedStatus.NO,
        raw_features={"posizione": "Via Carlo Goldoni 16 - PORDENONE"},
    )
    kwargs.update(overrides)
    return kwargs


def test_builds_a_listing_from_fully_normalized_data() -> None:
    listing = Listing(**_valid_listing_kwargs())

    assert listing.reference == "V2645"
    assert listing.transaction is PropertyTransaction.SALE
    assert listing.city == "Pordenone"
    assert listing.floor_level == 2
    assert listing.parking_type is ParkingType.COVERED
    assert listing.raw_features == {"posizione": "Via Carlo Goldoni 16 - PORDENONE"}


@pytest.mark.parametrize("year_built", [499, 2036])
def test_rejects_year_built_outside_the_plausible_range(year_built: int) -> None:
    with pytest.raises(ValidationError):
        Listing(**_valid_listing_kwargs(year_built=year_built))


@pytest.mark.parametrize("year_built", [500, 2035, 700, 2027])
def test_accepts_year_built_within_or_on_the_plausible_range(year_built: int) -> None:
    listing = Listing(**_valid_listing_kwargs(year_built=year_built))

    assert listing.year_built == year_built


def test_allows_year_built_to_be_unknown() -> None:
    listing = Listing(**_valid_listing_kwargs(year_built=None))

    assert listing.year_built is None
