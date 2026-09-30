"""In-memory `ListingRepository`: the whole catalogue is a list held in
process. Sized for the current export (~100 listings) and swappable behind
`ListingRepository` if that changes."""

from __future__ import annotations

from app.domain.listing import Listing
from app.domain.search import SearchCriteria


class InMemoryListingRepository:
    def __init__(self, listings: list[Listing]) -> None:
        self._listings = list(listings)

    def search(self, criteria: SearchCriteria) -> list[Listing]:
        return [listing for listing in self._listings if self._matches(listing, criteria)]

    def get_by_reference(self, reference: str) -> Listing | None:
        for listing in self._listings:
            if listing.reference == reference:
                return listing
        return None

    def _matches(self, listing: Listing, criteria: SearchCriteria) -> bool:
        if criteria.transaction is not None and listing.transaction is not criteria.transaction:
            return False

        minimums = (
            (criteria.price_min, listing.price_eur),
            (criteria.surface_min, listing.surface_sqm),
            (criteria.bedrooms_min, listing.bedrooms),
            (criteria.bathrooms_min, listing.bathrooms),
            (criteria.floor_level_min, listing.floor_level),
            (criteria.terraces_min, listing.terraces),
        )
        for bound, value in minimums:
            if bound is not None and not _at_least(value, bound):
                return False

        if criteria.price_max is not None and not _at_most(listing.price_eur, criteria.price_max):
            return False

        exact_matches = (
            (criteria.energy_class, listing.energy_class),
            (criteria.area_type, listing.area_type),
            (criteria.furnished, listing.furnished),
            (criteria.garden, listing.garden),
            (criteria.cellar, listing.cellar),
        )
        for wanted, value in exact_matches:
            if wanted is not None and value != wanted:
                return False

        # Place names come from the LLM's reading of free text, so they are
        # compared case-insensitively rather than literally.
        case_insensitive_matches = (
            (criteria.city, listing.city),
            (criteria.province, listing.province),
            (criteria.property_type, listing.property_type),
        )
        for wanted, value in case_insensitive_matches:
            if wanted is not None and not _equal_ignoring_case(value, wanted):
                return False

        if criteria.has_parking is not None and _has_parking(listing) is not criteria.has_parking:
            return False

        if criteria.keywords:
            haystack = _searchable_text(listing)
            if not all(keyword.casefold() in haystack for keyword in criteria.keywords):
                return False

        return True


def _at_least(value: int | None, bound: int) -> bool:
    # An unknown value cannot be shown to satisfy the bound, so it fails it.
    return value is not None and value >= bound


def _at_most(value: int | None, bound: int) -> bool:
    return value is not None and value <= bound


def _equal_ignoring_case(value: str | None, wanted: str) -> bool:
    return value is not None and value.casefold() == wanted.casefold()


def _has_parking(listing: Listing) -> bool:
    return listing.parking_spaces is not None and listing.parking_spaces > 0


def _searchable_text(listing: Listing) -> str:
    """Everything a free-text keyword may legitimately match: the prose the
    agency wrote, plus the feature values that stayed untyped."""
    parts = [listing.title, listing.description, *listing.raw_features.keys(), *listing.raw_features.values()]
    return " ".join(part for part in parts if part).casefold()
