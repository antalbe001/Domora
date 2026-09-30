from typing import Any

from app.domain.listing import Listing, PropertyTransaction
from app.llm.listing_tools import ListingTools
from app.repositories.in_memory import InMemoryListingRepository


def _listing(reference: str, **overrides: Any) -> Listing:
    fields: dict[str, Any] = {
        "reference": reference,
        "transaction": PropertyTransaction.SALE,
        "title": f"{reference} – Appartamento",
        "url": f"https://example.test/annunci/{reference.lower()}/",
        "price_eur": 100_000,
        "city": "Pordenone",
    }
    fields.update(overrides)
    return Listing(**fields)


def _tools(*listings: Listing, max_results: int = 15) -> ListingTools:
    return ListingTools(
        repository=InMemoryListingRepository(list(listings)), max_results=max_results
    )


def test_search_returns_the_matching_listings_with_their_total() -> None:
    tools = _tools(
        _listing("V1", price_eur=100_000),
        _listing("V2", price_eur=300_000),
    )

    result = tools.execute("search_listings", {"price_max": 150_000})

    assert result.payload["total"] == 1
    assert [found["reference"] for found in result.payload["listings"]] == ["V1"]


def test_search_caps_the_listings_but_reports_the_true_total() -> None:
    tools = _tools(*(_listing(f"V{index}") for index in range(10)), max_results=3)

    result = tools.execute("search_listings", {})

    assert result.payload["total"] == 10
    assert len(result.payload["listings"]) == 3
    assert result.payload["truncated"] is True


def test_search_is_not_flagged_as_truncated_when_everything_fits() -> None:
    tools = _tools(_listing("V1"), _listing("V2"), max_results=3)

    result = tools.execute("search_listings", {})

    assert result.payload["truncated"] is False


def test_search_orders_by_price_ascending_with_unknown_prices_last() -> None:
    tools = _tools(
        _listing("V1", price_eur=200_000),
        _listing("V2", price_eur=None),
        _listing("V3", price_eur=100_000),
    )

    result = tools.execute("search_listings", {})

    assert [found["reference"] for found in result.payload["listings"]] == ["V3", "V1", "V2"]


def test_search_also_hands_back_the_listings_for_the_frontend_to_render() -> None:
    tools = _tools(_listing("V1"))

    result = tools.execute("search_listings", {})

    assert [listing.reference for listing in result.listings] == ["V1"]


def test_search_reports_invalid_input_to_the_model_instead_of_raising() -> None:
    tools = _tools(_listing("V1"))

    result = tools.execute("search_listings", {"price_max": "un sacco di soldi"})

    assert "error" in result.payload
    assert result.listings == []


def test_get_listing_detail_returns_every_field_of_the_listing() -> None:
    tools = _tools(_listing("V1", bedrooms=3))

    result = tools.execute("get_listing_detail", {"reference": "V1"})

    assert result.payload["listing"]["reference"] == "V1"
    assert result.payload["listing"]["bedrooms"] == 3
    assert [listing.reference for listing in result.listings] == ["V1"]


def test_get_listing_detail_reports_a_missing_reference() -> None:
    tools = _tools(_listing("V1"))

    result = tools.execute("get_listing_detail", {"reference": "V999"})

    assert "error" in result.payload
    assert result.listings == []


def test_an_unknown_tool_is_reported_rather_than_raising() -> None:
    result = _tools(_listing("V1")).execute("delete_everything", {})

    assert "error" in result.payload
