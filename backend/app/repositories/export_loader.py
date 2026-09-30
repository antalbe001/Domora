"""Reads the scraper's annunci.json export and turns it into `Listing`
objects for the repository.

A record the schema rejects is skipped and logged, never fatal: the agency
publishing one odd value should cost us that listing, not the whole site.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.listing import Listing
from app.normalization.listing_mapper import to_listing

logger = logging.getLogger(__name__)


def load_listings(path: Path) -> list[Listing]:
    export = json.loads(Path(path).read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = export.get("listings") or []

    listings: list[Listing] = []
    for record in records:
        try:
            listings.append(to_listing(record))
        except (ValidationError, ValueError, KeyError) as error:
            logger.warning(
                "Skipping listing %s from %s: %s",
                record.get("reference", "<no reference>"),
                path,
                error,
            )

    if skipped := len(records) - len(listings):
        logger.warning("Skipped %d of %d listings from %s", skipped, len(records), path)

    return listings
