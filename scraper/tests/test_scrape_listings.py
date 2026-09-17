import json
import tempfile
import unittest
from pathlib import Path

from scrape_listings import (
    ScrapeError,
    ensure_unique_references,
    parse_listing,
    parse_listing_index,
    write_json_atomically,
)


FIXTURES = Path(__file__).parent / "fixtures"


class ParseListingTests(unittest.TestCase):
    def test_normalizes_known_fields_and_preserves_extra_features(self) -> None:
        html = (FIXTURES / "listing.html").read_text(encoding="utf-8")

        listing = parse_listing(
            "https://salamonimmobiliare.com/annunci/v2645-esempio/", html, "sale"
        )

        self.assertEqual(listing["reference"], "V2645")
        self.assertEqual(listing["transaction"], "sale")
        self.assertEqual(listing["price_eur"], 175000)
        self.assertEqual(listing["surface_sqm"], 188)
        self.assertEqual(listing["bedrooms"], 2)
        self.assertEqual(listing["bathrooms"], 1)
        self.assertEqual(listing["floor"], 1)
        self.assertEqual(listing["year_built"], 1980)
        self.assertIsNone(listing["province"])
        self.assertEqual(listing["description"], "Una descrizione introduttiva. Con un secondo paragrafo.")
        self.assertEqual(listing["features"]["superficie_terrazzo"], "30 mq")
        self.assertEqual(listing["features"]["accessori"], ["Garage", "Cantina"])

    def test_finds_detail_and_pagination_urls_only(self) -> None:
        html = (FIXTURES / "listing_index.html").read_text(encoding="utf-8")

        details, pages = parse_listing_index(
            html, "https://salamonimmobiliare.com/cerca-proprieta/comprare/"
        )

        self.assertEqual(
            details,
            {
                "https://salamonimmobiliare.com/annunci/v2644-esempio/",
                "https://salamonimmobiliare.com/annunci/v2645-esempio/",
            },
        )
        self.assertEqual(
            pages,
            {"https://salamonimmobiliare.com/cerca-proprieta/comprare/page/2/"},
        )

    def test_rejects_conflicting_references(self) -> None:
        with self.assertRaises(ScrapeError):
            ensure_unique_references(
                [
                    {"reference": "V1", "url": "https://example.test/one/"},
                    {"reference": "V1", "url": "https://example.test/two/"},
                ]
            )

    def test_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "annunci.json"
            write_json_atomically({"listings": []}, destination)

            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), {"listings": []})


if __name__ == "__main__":
    unittest.main()
