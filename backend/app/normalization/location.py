"""Parses the raw `features["posizione"]` string scraped from listing pages
(e.g. "Via Carlo Goldoni 16 - PORDENONE") into the canonical location
fields of `Listing` (address, city, province)."""

from __future__ import annotations

from dataclasses import dataclass

# Every comune (and known frazione) appearing in the export. Mostly
# provincia di Pordenone, but the catalogue reaches into Venezia, so this is
# a real lookup and not a constant. An unmapped comune degrades to
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
    "Brugnera": "PN",
    "Budoia": "PN",
    "Casarsa Della Delizia": "PN",
    "Chions": "PN",
    "Claut": "PN",
    "Fontanafredda": "PN",
    "Montereale Valcellina": "PN",
    "Porcia": "PN",
    "Zoppola": "PN",
    "San Michele Al Tagliamento": "VE",
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
