import pytest

from app.domain.listing import AreaType, FurnishedStatus, KitchenType, ParkingType
from app.normalization.features import (
    parse_area_type,
    parse_cellar,
    parse_furnished,
    parse_garden,
    parse_kitchen,
    parse_parking,
    parse_terraces,
)


@pytest.mark.parametrize("value, expected", [("Si", True), ("No", False)])
def test_parse_garden(value: str, expected: bool) -> None:
    assert parse_garden(value) is expected


@pytest.mark.parametrize("value, expected", [("Si", True), ("No", False)])
def test_parse_cellar(value: str, expected: bool) -> None:
    assert parse_cellar(value) is expected


@pytest.mark.parametrize("value, expected", [("0", 0), ("1", 1), ("2", 2), ("3", 3)])
def test_parse_terraces(value: str, expected: int) -> None:
    assert parse_terraces(value) == expected


@pytest.mark.parametrize(
    "value, expected_spaces, expected_type",
    [
        ("0", 0, ParkingType.NONE),
        ("1", 1, ParkingType.COVERED),
        ("2", 2, ParkingType.COVERED),
        ("Posto auto scoperto", 1, ParkingType.OPEN),
        ("Posto auto coperto", 1, ParkingType.COVERED),
        ("Doppio", 2, ParkingType.DOUBLE),
        ("Posto auto condominiale", 1, ParkingType.CONDOMINIAL),
    ],
)
def test_parse_parking(value: str, expected_spaces: int, expected_type: ParkingType) -> None:
    spaces, parking_type = parse_parking(value)

    assert spaces == expected_spaces
    assert parking_type is expected_type


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Cucina separata", KitchenType.SEPARATE),
        ("Open space", KitchenType.OPEN_SPACE),
        ("Angolo cottura", KitchenType.KITCHENETTE),
    ],
)
def test_parse_kitchen(value: str, expected: KitchenType) -> None:
    assert parse_kitchen(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Centrale", AreaType.CENTRAL),
        ("Periferia", AreaType.SUBURB),
        ("Semicentrale", AreaType.SEMI_CENTRAL),
    ],
)
def test_parse_area_type(value: str, expected: AreaType) -> None:
    assert parse_area_type(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Si", FurnishedStatus.YES),
        ("No", FurnishedStatus.NO),
        ("Parzialmente", FurnishedStatus.PARTIAL),
    ],
)
def test_parse_furnished(value: str, expected: FurnishedStatus) -> None:
    assert parse_furnished(value) is expected
