from app.normalization.location import parse_location


def test_parses_address_city_and_province_from_the_standard_format() -> None:
    parsed = parse_location("Via Carlo Goldoni 16 - PORDENONE")

    assert parsed.address == "Via Carlo Goldoni 16"
    assert parsed.city == "Pordenone"
    assert parsed.province == "PN"


def test_parses_the_city_only_exception_with_no_dash() -> None:
    parsed = parse_location("PRATA DI PORDENONE")

    assert parsed.address is None
    assert parsed.city == "Prata Di Pordenone"
    assert parsed.province == "PN"


def test_degrades_to_unknown_province_for_an_unmapped_comune() -> None:
    parsed = parse_location("Via Roma 1 - VENEZIA")

    assert parsed.address == "Via Roma 1"
    assert parsed.city == "Venezia"
    assert parsed.province is None
