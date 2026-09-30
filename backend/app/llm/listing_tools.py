"""Runs the tools the model asks for against the repository.

Each result has two audiences: `payload` is the JSON handed back to the
model, `listings` are the domain objects the frontend renders as cards. A
tool never raises at the model — a bad reference or an unparseable argument
comes back as an `error` the model can recover from in its next turn.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.domain.listing import Listing
from app.domain.search import SearchCriteria
from app.llm.tools import GET_LISTING_DETAIL, SEARCH_LISTINGS
from app.repositories.listing_repository import ListingRepository

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 15

# What the model needs to describe and compare listings. Deliberately not the
# whole record: the full set is one `get_listing_detail` away.
_SUMMARY_FIELDS = (
    "reference",
    "transaction",
    "title",
    "url",
    "property_type",
    "price_eur",
    "city",
    "province",
    "surface_sqm",
    "bedrooms",
    "bathrooms",
    "floor_label",
    "energy_class",
)


@dataclass(frozen=True)
class ToolResult:
    payload: dict[str, Any]
    listings: list[Listing] = field(default_factory=list)


class ListingTools:
    def __init__(
        self,
        repository: ListingRepository,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> None:
        self._repository = repository
        self._max_results = max_results

    def execute(self, name: str, tool_input: dict[str, Any]) -> ToolResult:
        if name == SEARCH_LISTINGS.name:
            return self._search(tool_input)
        if name == GET_LISTING_DETAIL.name:
            return self._detail(tool_input)

        logger.warning("Model asked for unknown tool %r", name)
        return ToolResult(payload={"error": f"Unknown tool {name!r}."})

    def _search(self, tool_input: dict[str, Any]) -> ToolResult:
        try:
            criteria = SearchCriteria.model_validate(tool_input)
        except ValidationError as error:
            return ToolResult(
                payload={
                    "error": "Invalid search arguments; fix them and try again.",
                    "details": error.errors(include_url=False),
                }
            )

        found = sorted(self._repository.search(criteria), key=_by_price)
        shown = found[: self._max_results]

        return ToolResult(
            payload={
                "total": len(found),
                "returned": len(shown),
                "truncated": len(found) > len(shown),
                "listings": [_summarize(listing) for listing in shown],
            },
            listings=shown,
        )

    def _detail(self, tool_input: dict[str, Any]) -> ToolResult:
        reference = str(tool_input.get("reference", "")).strip()
        listing = self._repository.get_by_reference(reference) if reference else None
        if listing is None:
            return ToolResult(
                payload={"error": f"No listing with reference {reference!r}."}
            )

        return ToolResult(
            payload={"listing": listing.model_dump(mode="json")},
            listings=[listing],
        )


def _by_price(listing: Listing) -> tuple[int, int]:
    """Cheapest first; a listing with no price cannot be placed among the
    others, so it goes last."""
    if listing.price_eur is None:
        return (1, 0)
    return (0, listing.price_eur)


def _summarize(listing: Listing) -> dict[str, Any]:
    record = listing.model_dump(mode="json")
    return {name: record[name] for name in _SUMMARY_FIELDS}
