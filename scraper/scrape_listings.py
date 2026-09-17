#!/usr/bin/env python3
"""Export the active Salamon Immobiliare listings to a local JSON file."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


SOURCE_URLS = {
    "sale": "https://salamonimmobiliare.com/cerca-proprieta/comprare/",
    "rent": "https://salamonimmobiliare.com/cerca-proprieta/affittare/",
}
REQUEST_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
MAX_LISTING_PAGES_PER_TRANSACTION = 100
USER_AGENT = "SalamonImmobiliareAuthorizedExporter/1.0"
PLACEHOLDER_VALUES = {"", "-", "n_a", "n_d", "nd", "non_disponibile", "valore"}

NORMALIZED_FIELDS = (
    "reference",
    "transaction",
    "title",
    "url",
    "description",
    "price_eur",
    "property_type",
    "address",
    "city",
    "province",
    "surface_sqm",
    "bedrooms",
    "bathrooms",
    "floor",
    "year_built",
    "heating",
    "energy_class",
)

LABEL_TO_FIELD = {
    "prezzo": "price_eur",
    "prezzo_vendita": "price_eur",
    "prezzo_affitto": "price_eur",
    "tipologia": "property_type",
    "tipologia_immobile": "property_type",
    "indirizzo": "address",
    "via": "address",
    "comune": "city",
    "citta": "city",
    "localita": "city",
    "provincia": "province",
    "superficie": "surface_sqm",
    "superficie_commerciale": "surface_sqm",
    "camere": "bedrooms",
    "bagni": "bathrooms",
    "piano": "floor",
    "anno_di_costruzione": "year_built",
    "riscaldamento": "heating",
    "classe_energetica": "energy_class",
}


class ScrapeError(RuntimeError):
    """Raised when the site cannot be exported safely."""


def normalized_key(value: str) -> str:
    """Convert a human-readable Italian label into a stable JSON key."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_value.lower())).strip("_")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return None if normalized_key(cleaned) in PLACEHOLDER_VALUES else cleaned or None


def parse_italian_number(value: str | None) -> int | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None

    number = re.search(r"\d[\d.,]*", cleaned)
    if number is None:
        return None

    token = number.group(0)
    # Italian amounts use dots for thousands and commas for decimals.
    token = token.replace(".", "").split(",", maxsplit=1)[0]
    return int(token)


def parse_floor(value: str | None) -> int | str | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    return int(cleaned) if cleaned.isdigit() else cleaned


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") + "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def text_from_description(soup: BeautifulSoup) -> str | None:
    description = soup.select_one(".general-content")
    return clean_text(description.get_text(" ", strip=True) if description else None)


def empty_listing(url: str, transaction: str) -> dict[str, Any]:
    listing = {field: None for field in NORMALIZED_FIELDS}
    listing["url"] = canonical_url(url)
    listing["transaction"] = transaction
    listing["features"] = {}
    return listing


def add_feature(features: dict[str, Any], key: str, value: str) -> None:
    if key not in features:
        features[key] = value
    elif isinstance(features[key], list):
        features[key].append(value)
    else:
        features[key] = [features[key], value]


def set_normalized_value(listing: dict[str, Any], field: str, value: str) -> None:
    if field in {"price_eur", "surface_sqm", "bedrooms", "bathrooms", "year_built"}:
        parsed: Any = parse_italian_number(value)
    elif field == "floor":
        parsed = parse_floor(value)
    else:
        parsed = clean_text(value)

    # A duplicate real value is retained in features; placeholders never replace real data.
    if parsed is None:
        return
    if listing[field] is None:
        listing[field] = parsed
    elif listing[field] != parsed:
        add_feature(listing["features"], f"duplicate_{field}", str(parsed))


def parse_listing(url: str, html: str, transaction: str) -> dict[str, Any]:
    """Parse one detail page into the public JSON contract."""
    soup = BeautifulSoup(html, "html.parser")
    listing = empty_listing(url, transaction)

    heading = soup.select_one("h1")
    title = clean_text(heading.get_text(" ", strip=True) if heading else None)
    if title is None and soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True).replace(" - Salamon Immobiliare", ""))
    listing["title"] = title
    listing["description"] = text_from_description(soup)

    if title:
        reference = re.search(r"\b(?:[A-Z]\d+|\d{5,})\b", title, flags=re.IGNORECASE)
        listing["reference"] = reference.group(0).upper() if reference else None

    for row in soup.select(".tr"):
        label_element = row.select_one(".td")
        value_element = row.select_one(".td-value")
        if label_element is None or value_element is None:
            continue

        label = clean_text(label_element.get_text(" ", strip=True))
        value = clean_text(value_element.get_text(" ", strip=True))
        if label is None or value is None:
            continue

        label_key = normalized_key(label)
        if label_key == "prezzo_affitto":
            listing["transaction"] = "rent"
        elif label_key == "prezzo_vendita":
            listing["transaction"] = "sale"

        normalized_field = LABEL_TO_FIELD.get(label_key)
        if normalized_field:
            set_normalized_value(listing, normalized_field, value)
        else:
            add_feature(listing["features"], label_key, value)

    return listing


def parse_listing_index(html: str, page_url: str) -> tuple[set[str], set[str]]:
    """Return detail-page links and pagination links found on a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    base = urlparse(page_url)
    detail_urls: set[str] = set()
    pagination_urls: set[str] = set()

    for anchor in soup.select("a[href]"):
        absolute_url = urljoin(page_url, anchor["href"])
        parsed = urlparse(absolute_url)
        if parsed.netloc != base.netloc:
            continue

        canonical = canonical_url(absolute_url)
        if "/annunci/" in parsed.path:
            detail_urls.add(canonical)
        elif (
            anchor.get("rel") and "next" in anchor.get("rel", [])
        ) or "page-numbers" in anchor.get("class", []) or anchor.find_parent(class_=re.compile("pagination", re.I)):
            source_path = base.path.rstrip("/") + "/"
            if parsed.path.startswith(source_path):
                pagination_urls.add(canonical)

    pagination_urls.discard(canonical_url(page_url))
    return detail_urls, pagination_urls


class SiteClient:
    def __init__(self, delay_seconds: float = REQUEST_DELAY_SECONDS) -> None:
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request_at: float | None = None

    def get_html(self, url: str) -> str:
        for attempt in range(1, MAX_RETRIES + 1):
            if self._last_request_at is not None:
                elapsed = time.monotonic() - self._last_request_at
                time.sleep(max(0, self.delay_seconds - elapsed))

            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                self._last_request_at = time.monotonic()
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise ScrapeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                return response.text
            except (requests.RequestException, ScrapeError) as error:
                if attempt == MAX_RETRIES:
                    raise ScrapeError(f"Unable to fetch {url}: {error}") from error
                time.sleep(self.delay_seconds * attempt)

        raise AssertionError("unreachable")


def collect_listing_urls(client: SiteClient, source_url: str) -> set[str]:
    pending = [canonical_url(source_url)]
    visited: set[str] = set()
    listings: set[str] = set()

    while pending:
        page_url = pending.pop()
        if page_url in visited:
            continue
        if len(visited) >= MAX_LISTING_PAGES_PER_TRANSACTION:
            raise ScrapeError(f"Pagination limit reached while crawling {source_url}")

        visited.add(page_url)
        detail_urls, pagination_urls = parse_listing_index(client.get_html(page_url), page_url)
        listings.update(detail_urls)
        pending.extend(sorted(pagination_urls - visited))

    if not listings:
        raise ScrapeError(f"No listing URLs found at {source_url}")
    return listings


def ensure_unique_references(listings: Iterable[dict[str, Any]]) -> None:
    references: dict[str, str] = {}
    for listing in listings:
        reference = listing["reference"]
        if reference is None:
            raise ScrapeError(f"Missing reference for {listing['url']}")
        if reference in references and references[reference] != listing["url"]:
            raise ScrapeError(
                f"Reference {reference} is used by both {references[reference]} and {listing['url']}"
            )
        references[reference] = listing["url"]


def build_export(client: SiteClient) -> dict[str, Any]:
    urls_by_transaction = {
        transaction: collect_listing_urls(client, source_url)
        for transaction, source_url in SOURCE_URLS.items()
    }
    listing_urls = {
        url: transaction
        for transaction, urls in urls_by_transaction.items()
        for url in urls
    }
    listings = [
        parse_listing(url, client.get_html(url), transaction)
        for url, transaction in sorted(listing_urls.items())
    ]
    ensure_unique_references(listings)
    listings.sort(key=lambda listing: (listing["transaction"], listing["reference"], listing["url"]))

    counts = defaultdict(int)
    for listing in listings:
        counts[listing["transaction"]] += 1

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_urls": SOURCE_URLS,
        "count": {"total": len(listings), "sale": counts["sale"], "rent": counts["rent"]},
        "listings": listings,
    }


def write_json_atomically(export: dict[str, Any], output_path: Path) -> None:
    output_path = output_path.resolve()
    if not output_path.parent.exists():
        raise ScrapeError(f"Output directory does not exist: {output_path.parent}")

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_path.parent, delete=False, suffix=".tmp"
        ) as temporary_file:
            temporary_name = temporary_file.name
            json.dump(export, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_name, output_path)
    except OSError as error:
        raise ScrapeError(f"Unable to write {output_path}: {error}") from error
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("annunci.json"),
        help="Where to write the JSON export (default: annunci.json)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    started_at = time.monotonic()
    try:
        export = build_export(SiteClient())
        write_json_atomically(export, arguments.output)
    except ScrapeError as error:
        print(f"Export failed: {error}")
        return 1

    elapsed = time.monotonic() - started_at
    count = export["count"]
    print(
        f"Exported {count['total']} listings "
        f"({count['sale']} sale, {count['rent']} rent) to {arguments.output} in {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
