import pytest

from app.domain.listing import EnergyClass, HeatingType
from app.normalization.fields import parse_energy_class, parse_floor, parse_heating


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Autonomo", HeatingType.AUTONOMOUS),
        ("Centralizzato", HeatingType.CENTRALIZED),
        ("Contacalorie", HeatingType.HEAT_METER),
        ("No riscaldamento", HeatingType.NONE),
    ],
)
def test_parse_heating(value: str, expected: HeatingType) -> None:
    assert parse_heating(value) is expected


def test_parse_heating_is_unknown_when_absent() -> None:
    assert parse_heating(None) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("A+", EnergyClass.A_PLUS),
        ("A", EnergyClass.A),
        ("B", EnergyClass.B),
        ("C", EnergyClass.C),
        ("D", EnergyClass.D),
        ("E", EnergyClass.E),
        ("F", EnergyClass.F),
        ("G", EnergyClass.G),
    ],
)
def test_parse_energy_class(value: str, expected: EnergyClass) -> None:
    assert parse_energy_class(value) is expected


@pytest.mark.parametrize("value", [None, "In fase di redazione"])
def test_parse_energy_class_is_unknown_for_absent_and_placeholder_values(
    value: str | None,
) -> None:
    assert parse_energy_class(value) is None


@pytest.mark.parametrize(
    "value, expected_label, expected_level",
    [
        (2, "2", 2),
        (0, "0", 0),
        ("terra", "terra", 0),
        ("rialzato", "rialzato", 0),
        ("5 oltre", "5 oltre", 5),
    ],
)
def test_parse_floor_keeps_a_display_label_and_derives_a_sortable_level(
    value: int | str, expected_label: str, expected_level: int
) -> None:
    parsed = parse_floor(value)

    assert parsed.label == expected_label
    assert parsed.level == expected_level


def test_parse_floor_is_unknown_when_absent() -> None:
    parsed = parse_floor(None)

    assert parsed.label is None
    assert parsed.level is None
