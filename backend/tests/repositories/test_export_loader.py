import json
import logging
from pathlib import Path
from typing import Any

from app.repositories.export_loader import load_listings


def _export(*records: dict[str, Any]) -> dict[str, Any]:
    """The envelope the scraper writes around the listings."""
    return {
        "generated_at": "2026-08-30T14:15:08.781379Z",
        "count": {"total": len(records)},
        "listings": list(records),
    }


def _record(reference: str, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "reference": reference,
        "transaction": "sale",
        "title": f"{reference} – Appartamento",
        "url": f"https://example.test/annunci/{reference.lower()}/",
        "price_eur": 150_000,
        "features": {"posizione": "Via Roma 1 - PORDENONE"},
    }
    record.update(overrides)
    return record


def _write_export(directory: Path, export: dict[str, Any]) -> Path:
    path = directory / "annunci.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    return path


def test_loads_every_listing_of_the_export(tmp_path: Path) -> None:
    path = _write_export(tmp_path, _export(_record("V1"), _record("V2")))

    listings = load_listings(path)

    assert [listing.reference for listing in listings] == ["V1", "V2"]
    assert listings[0].city == "Pordenone"


def test_skips_an_invalid_record_and_keeps_the_rest(
    tmp_path: Path, caplog: Any
) -> None:
    path = _write_export(
        tmp_path,
        _export(_record("V1"), _record("V2", year_built=99_999), _record("V3")),
    )

    with caplog.at_level(logging.WARNING):
        listings = load_listings(path)

    assert [listing.reference for listing in listings] == ["V1", "V3"]
    assert "V2" in caplog.text


def test_returns_nothing_for_an_export_with_no_listings(tmp_path: Path) -> None:
    path = _write_export(tmp_path, _export())

    assert load_listings(path) == []
