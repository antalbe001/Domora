"""Parses the raw `features["posizione"]` string scraped from listing pages
(e.g. "Via Carlo Goldoni 16 - PORDENONE") into the canonical location
fields of `Listing` (address, city, province)."""

from __future__ import annotations

from dataclasses import dataclass

# Comuni (and known frazioni) observed in the Salamon Immobiliare export,
# all in provincia di Pordenone. An unmapped comune degrades to
# province=None rather than raising — new comuni may appear in future
# scrapes and should not break loading.
COMUNE_TO_PROVINCE: dict[str, str] = {
    "Pordenone": "PN",
    "Cordenons": "PN",
    "Azzano Decimo": "PN",
    "Sacile": "PN",
    "Aviano": "PN",
    "Fiume Veneto": "PN",
    "San Quirino": "PN",
    "Pasiano Di Pordenone": "PN",
    "Prata Di Pordenone": "PN",
    "Maniago": "PN",
    "Roveredo In Piano": "PN",
    # Frazioni/quartieri (non comuni a sé) osservati nell'export, mappati
    # comunque alla provincia del comune di appartenenza.
    "Borgomeduna": "PN",
    "Visinale Di Pasiano": "PN",
}


@dataclass(frozen=True)
class ParsedLocation:
    address: str | None
    city: str | None
    province: str | None


def parse_location(posizione: str) -> ParsedLocation:
    address_part, separator, city_part = posizione.rpartition(" - ")
    city = city_part.strip().title()
    return ParsedLocation(
        address=address_part.strip() if separator else None,
        city=city,
        province=COMUNE_TO_PROVINCE.get(city),
    )
