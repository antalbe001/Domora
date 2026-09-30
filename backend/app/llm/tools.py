"""The tools the model is given, and their JSON schemas.

`search_listings` is generated from `SearchCriteria` rather than written by
hand, so the tool the model fills in and the filter the repository applies
cannot drift apart. Pydantic's output is then flattened for the model's
benefit: optionals become plain types (optionality is already expressed by
being absent from `required`), enums are inlined so their allowed values are
visible without following a `$ref`, and presentational noise is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.search import SearchCriteria

_NOISE_KEYS = frozenset({"title", "default"})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def _flatten(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_flatten(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node

    if reference := node.get("$ref"):
        target = definitions[reference.rsplit("/", maxsplit=1)[-1]]
        # Keep any sibling keys (a description, typically) over the target's.
        siblings = {key: value for key, value in node.items() if key != "$ref"}
        return _flatten({**target, **siblings}, definitions)

    if alternatives := node.get("anyOf"):
        non_null = [
            alternative
            for alternative in alternatives
            if alternative.get("type") != "null"
        ]
        siblings = {key: value for key, value in node.items() if key != "anyOf"}
        if len(non_null) == 1:
            return _flatten({**non_null[0], **siblings}, definitions)
        return _flatten({**siblings, "anyOf": non_null}, definitions)

    return {
        key: _flatten(value, definitions)
        for key, value in node.items()
        if key not in _NOISE_KEYS
    }


def _tool_schema(model: type[SearchCriteria]) -> dict[str, Any]:
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})
    flattened = _flatten(schema, definitions)
    # Nothing is mandatory: an empty criteria set means "everything".
    flattened["required"] = []
    return flattened


SEARCH_LISTINGS = ToolSpec(
    name="search_listings",
    description=(
        "Search the agency's catalogue of properties. Every parameter is "
        "optional and they combine with AND; omit the ones the user did not "
        "constrain. Returns the matching listings, capped, together with the "
        "true total so you can tell the user how many there are. A listing "
        "whose value for a filtered field is unknown does not match that "
        "filter."
    ),
    input_schema=_tool_schema(SearchCriteria),
)

GET_LISTING_DETAIL = ToolSpec(
    name="get_listing_detail",
    description=(
        "Fetch every known field of one listing by its agency reference. Use "
        "it when the user asks to know more about a specific property you "
        "have already shown them."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": (
                    "The agency reference of the listing, e.g. 'V2424' or "
                    "'120314'."
                ),
            }
        },
        "required": ["reference"],
    },
)

ALL_TOOLS = (SEARCH_LISTINGS, GET_LISTING_DETAIL)
