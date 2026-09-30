"""The port the rest of the backend depends on. Today there is one
implementation, in-memory; a SQL-backed one would translate the same
`SearchCriteria` into a query without anything upstream changing."""

from __future__ import annotations

from typing import Protocol

from app.domain.listing import Listing
from app.domain.search import SearchCriteria


class ListingRepository(Protocol):
    def search(self, criteria: SearchCriteria) -> list[Listing]:
        """Every listing matching all the criteria that are set."""
        ...

    def get_by_reference(self, reference: str) -> Listing | None:
        """The listing with that agency reference, if it exists."""
        ...
