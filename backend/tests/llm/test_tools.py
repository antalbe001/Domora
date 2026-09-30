from typing import Any

from app.llm.tools import GET_LISTING_DETAIL, SEARCH_LISTINGS


def _walk(node: Any) -> list[Any]:
    """Every nested node of a JSON-schema-shaped structure."""
    found = [node]
    if isinstance(node, dict):
        for value in node.values():
            found.extend(_walk(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk(value))
    return found


def test_search_listings_is_derived_from_the_search_criteria() -> None:
    schema = SEARCH_LISTINGS.input_schema

    assert SEARCH_LISTINGS.name == "search_listings"
    # The field list comes from SearchCriteria, so the two cannot drift.
    assert {"transaction", "city", "price_max", "bedrooms_min", "keywords"} <= set(
        schema["properties"]
    )


def test_every_search_field_is_optional() -> None:
    assert SEARCH_LISTINGS.input_schema.get("required", []) == []


def test_the_schema_carries_no_null_branches() -> None:
    """A "null" alternative invites the model to pass an explicit null instead
    of omitting the field."""
    nodes = _walk(SEARCH_LISTINGS.input_schema)

    assert not any(isinstance(node, dict) and node.get("type") == "null" for node in nodes)
    assert not any(isinstance(node, dict) and "anyOf" in node for node in nodes)


def test_enums_are_inlined_so_the_model_sees_the_allowed_values() -> None:
    schema = SEARCH_LISTINGS.input_schema

    assert schema["properties"]["transaction"]["enum"] == ["sale", "rent"]
    assert "$defs" not in schema
    assert not any(isinstance(node, dict) and "$ref" in node for node in _walk(schema))


def test_every_search_field_explains_itself_to_the_model() -> None:
    missing = [
        name
        for name, field in SEARCH_LISTINGS.input_schema["properties"].items()
        if not field.get("description")
    ]

    assert missing == []


def test_get_listing_detail_requires_a_reference() -> None:
    schema = GET_LISTING_DETAIL.input_schema

    assert GET_LISTING_DETAIL.name == "get_listing_detail"
    assert schema["required"] == ["reference"]
    assert schema["properties"]["reference"]["type"] == "string"
