from typing import Any

from app.domain.listing import (
    AreaType,
    EnergyClass,
    FurnishedStatus,
    Listing,
    ParkingType,
    PropertyTransaction,
)
from app.domain.search import SearchCriteria
from app.repositories.in_memory import InMemoryListingRepository


def _listing(reference: str, **overrides: Any) -> Listing:
    fields: dict[str, Any] = {
        "reference": reference,
        "transaction": PropertyTransaction.SALE,
        "title": f"{reference} – Appartamento",
        "url": f"https://example.test/annunci/{reference.lower()}/",
    }
    fields.update(overrides)
    return Listing(**fields)


def _references(listings: list[Listing]) -> list[str]:
    return [listing.reference for listing in listings]


def test_empty_criteria_return_every_listing() -> None:
    repository = InMemoryListingRepository([_listing("V1"), _listing("V2")])

    assert _references(repository.search(SearchCriteria())) == ["V1", "V2"]


def test_filters_by_transaction() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", transaction=PropertyTransaction.SALE),
            _listing("V2", transaction=PropertyTransaction.RENT),
        ]
    )

    found = repository.search(SearchCriteria(transaction=PropertyTransaction.RENT))

    assert _references(found) == ["V2"]


def test_filters_by_price_range_inclusively() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", price_eur=100_000),
            _listing("V2", price_eur=150_000),
            _listing("V3", price_eur=200_000),
        ]
    )

    found = repository.search(SearchCriteria(price_min=100_000, price_max=150_000))

    assert _references(found) == ["V1", "V2"]


def test_filters_by_minimum_surface_bedrooms_and_bathrooms() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", surface_sqm=60, bedrooms=1, bathrooms=1),
            _listing("V2", surface_sqm=120, bedrooms=3, bathrooms=2),
        ]
    )

    found = repository.search(
        SearchCriteria(surface_min=100, bedrooms_min=2, bathrooms_min=2)
    )

    assert _references(found) == ["V2"]


def test_excludes_listings_whose_filtered_number_is_unknown() -> None:
    """A null price/surface cannot be shown to satisfy a numeric bound, so a
    listing missing that value drops out rather than being assumed to fit."""
    repository = InMemoryListingRepository(
        [_listing("V1", price_eur=None), _listing("V2", price_eur=120_000)]
    )

    found = repository.search(SearchCriteria(price_max=150_000))

    assert _references(found) == ["V2"]


def test_filters_by_minimum_floor_level() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", floor_label="terra", floor_level=0),
            _listing("V2", floor_label="3", floor_level=3),
        ]
    )

    found = repository.search(SearchCriteria(floor_level_min=1))

    assert _references(found) == ["V2"]


def test_matches_the_city_regardless_of_case() -> None:
    repository = InMemoryListingRepository(
        [_listing("V1", city="Pordenone"), _listing("V2", city="Sacile")]
    )

    found = repository.search(SearchCriteria(city="pordenone"))

    assert _references(found) == ["V1"]


def test_filters_by_province_property_type_energy_class_and_area_type() -> None:
    repository = InMemoryListingRepository(
        [
            _listing(
                "V1",
                province="PN",
                property_type="Appartamento",
                energy_class=EnergyClass.B,
                area_type=AreaType.CENTRAL,
            ),
            _listing(
                "V2",
                province="PN",
                property_type="Terreno",
                energy_class=EnergyClass.G,
                area_type=AreaType.SUBURB,
            ),
        ]
    )

    found = repository.search(
        SearchCriteria(
            province="PN",
            property_type="Appartamento",
            energy_class=EnergyClass.B,
            area_type=AreaType.CENTRAL,
        )
    )

    assert _references(found) == ["V1"]


def test_filters_by_garden_and_cellar() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", garden=True, cellar=False),
            _listing("V2", garden=True, cellar=True),
        ]
    )

    found = repository.search(SearchCriteria(garden=True, cellar=True))

    assert _references(found) == ["V2"]


def test_filters_by_furnished_status() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", furnished=FurnishedStatus.NO),
            _listing("V2", furnished=FurnishedStatus.YES),
        ]
    )

    found = repository.search(SearchCriteria(furnished=FurnishedStatus.YES))

    assert _references(found) == ["V2"]


def test_filters_by_having_any_parking() -> None:
    """"con box/posto auto" is about having somewhere to park at all, not
    about which kind, so any non-zero parking satisfies it."""
    repository = InMemoryListingRepository(
        [
            _listing("V1", parking_spaces=0, parking_type=ParkingType.NONE),
            _listing("V2", parking_spaces=1, parking_type=ParkingType.COVERED),
            _listing("V3", parking_spaces=2, parking_type=ParkingType.DOUBLE),
        ]
    )

    found = repository.search(SearchCriteria(has_parking=True))

    assert _references(found) == ["V2", "V3"]


def test_filters_by_minimum_terraces() -> None:
    repository = InMemoryListingRepository(
        [_listing("V1", terraces=0), _listing("V2", terraces=2)]
    )

    found = repository.search(SearchCriteria(terraces_min=1))

    assert _references(found) == ["V2"]


def test_keywords_match_the_title_description_and_untyped_features() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", description="Appartamento completamente RISTRUTTURATO."),
            _listing("V2", title="V2 – Loft luminoso"),
            _listing("V3", raw_features={"ascensore": "Si"}),
            _listing("V4", description="Da ristrutturare."),
        ]
    )

    assert _references(repository.search(SearchCriteria(keywords=["ristrutturato"]))) == ["V1"]
    assert _references(repository.search(SearchCriteria(keywords=["luminoso"]))) == ["V2"]
    assert _references(repository.search(SearchCriteria(keywords=["ascensore"]))) == ["V3"]


def test_every_keyword_must_be_present() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", description="Ristrutturato e luminoso."),
            _listing("V2", description="Ristrutturato."),
        ]
    )

    found = repository.search(SearchCriteria(keywords=["ristrutturato", "luminoso"]))

    assert _references(found) == ["V1"]


def test_criteria_combine_with_and() -> None:
    repository = InMemoryListingRepository(
        [
            _listing("V1", city="Pordenone", price_eur=120_000, bedrooms=3),
            _listing("V2", city="Pordenone", price_eur=300_000, bedrooms=3),
            _listing("V3", city="Sacile", price_eur=120_000, bedrooms=3),
            _listing("V4", city="Pordenone", price_eur=120_000, bedrooms=1),
        ]
    )

    found = repository.search(
        SearchCriteria(city="Pordenone", price_max=150_000, bedrooms_min=2)
    )

    assert _references(found) == ["V1"]


def test_replacing_the_catalogue_swaps_what_searches_see() -> None:
    """How /admin/reload picks up a fresh export without a restart."""
    repository = InMemoryListingRepository([_listing("V1")])

    repository.replace([_listing("V2"), _listing("V3")])

    assert _references(repository.search(SearchCriteria())) == ["V2", "V3"]
    assert repository.get_by_reference("V1") is None


def test_finds_a_listing_by_its_agency_reference() -> None:
    repository = InMemoryListingRepository([_listing("V1"), _listing("V2")])

    assert repository.get_by_reference("V2").reference == "V2"
    assert repository.get_by_reference("V999") is None
