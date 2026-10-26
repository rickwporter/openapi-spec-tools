from typing import Any

import pytest

from openapi_spec_tools.expand import expand_schema
from openapi_spec_tools.expand import merge_schema


@pytest.mark.parametrize(
    ["base", "overlay", "expected"],
    [
        pytest.param(
            {
                "type": "object",
                "description": "base",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string", "format": "password"},
                },
                "required": ["id", "name"],
            },
            {
                "description": "overlay",
                "properties": {"name": {"type": "string", "description": "user"}},
                "required": ["name", "tag"],
            },
            {
                "type": "object",
                "description": "overlay",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string", "description": "user"},
                },
                "required": ["id", "name", "tag"],
            },
            id="replace-and-combine",
        ),
        pytest.param(
            {"type": "object"},
            {"properties": {"name": {"type": "string"}}, "required": ["name"]},
            {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            id="missing-base",
        ),
        pytest.param(
            {"type": "object", "properties": {"name": {"type": "string"}}},
            {},
            {"type": "object", "properties": {"name": {"type": "string"}}},
            id="empty-overlay",
        ),
        pytest.param(
            {"properties": {"name": {"type": "string"}}, "required": ["name"]},
            {"properties": "bad", "required": "name"},
            {"properties": "bad", "required": "name"},
            id="non-collection",
        ),
    ],
)
def test_merge_schema(base: dict[str, Any], overlay: dict[str, Any], expected: dict[str, Any]) -> None:
    assert expected == merge_schema(base, overlay)


def test_merge_schema_copies() -> None:
    base = {"properties": {"name": {"type": "string"}}, "required": ["name"]}
    overlay = {"properties": {"tag": {"type": "string"}}, "required": ["tag"]}
    merged = merge_schema(base, overlay)

    merged["properties"]["name"]["type"] = "integer"
    merged["required"].append("extra")

    assert base == {"properties": {"name": {"type": "string"}}, "required": ["name"]}
    assert overlay == {"properties": {"tag": {"type": "string"}}, "required": ["tag"]}


PET_COMPONENTS = {
    "schemas": {
        "Pet": {
            "type": "object",
            "description": "A pet",
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            "required": ["name"],
        },
        "ComposedPet": {
            "description": "Pet plus extra",
            "allOf": [
                {"$ref": "#/components/schemas/Pet"},
                {
                    "type": "object",
                    "required": ["tag"],
                    "properties": {"tag": {"type": "string"}},
                },
            ],
        },
    }
}

LOOP_COMPONENTS = {
    "schemas": {
        "LoopA": {
            "allOf": [
                {"$ref": "#/components/schemas/LoopB"},
                {"type": "object", "properties": {"fromA": {"type": "string"}}},
            ],
        },
        "LoopB": {
            "allOf": [
                {"$ref": "#/components/schemas/LoopA"},
                {"type": "object", "properties": {"fromB": {"type": "integer"}}},
            ],
        },
        "LoopC": [],
    }
}

EXPANDED_PET = {
    "type": "object",
    "description": "A pet",
    "properties": {
        "id": {"type": "integer", "x-reference": "Pet"},
        "name": {"type": "string", "x-reference": "Pet"},
    },
    "required": ["name"],
    "x-reference": "Pet",
}

ENUM_COMPONENTS = {
    "schemas": {
        "Status": {
            "type": "string",
            "enum": ["open", "closed"],
        },
        "EmptyStatus": {
            "type": "string",
            "enum": [],
        },
        "BadStatus": {
            "type": "string",
            "enum": "open",
        },
        "LabeledStatus": {
            "description": "A labeled status",
            "allOf": [
                {"$ref": "#/components/schemas/Status"},
                {"description": "labeled"},
            ],
        },
        "Pet": {
            "type": "object",
            "properties": {
                "status": {"$ref": "#/components/schemas/Status"},
                "name": {"type": "string"},
            },
        },
    }
}

EXPANDED_STATUS = {
    "type": "string",
    "enum": ["open", "closed"],
    "x-reference": "Status",
    "x-enum": "Status",
}


@pytest.mark.parametrize(
    ["schema", "components", "name", "expected"],
    [
        pytest.param(None, {}, None, {}, id="none"),
        pytest.param({}, {}, None, {}, id="empty"),
        pytest.param(
            {"type": "object", "properties": {"name": {"type": "string"}}},
            {},
            None,
            {"type": "object", "properties": {"name": {"type": "string"}}},
            id="plain",
        ),
        pytest.param({"$ref": "#/components/schemas/Pet"}, PET_COMPONENTS, None, EXPANDED_PET, id="ref"),
        pytest.param(
            {"$ref": "#/components/schemas/Missing"},
            PET_COMPONENTS,
            None,
            {"$ref": "#/components/schemas/Missing"},
            id="missing-ref",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Missing", "description": "still here"},
            PET_COMPONENTS,
            None,
            {"$ref": "#/components/schemas/Missing", "description": "still here"},
            id="missing-ref-sibling",
        ),
        pytest.param(
            {"type": "object", "properties": {"pet": {"$ref": "#/components/schemas/Missing"}}},
            PET_COMPONENTS,
            None,
            {"type": "object", "properties": {"pet": {"$ref": "#/components/schemas/Missing"}}},
            id="missing-property-ref",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Pet", "description": "Custom pet"},
            PET_COMPONENTS,
            None,
            {**EXPANDED_PET, "description": "Custom pet"},
            id="ref-sibling",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/ComposedPet"},
            PET_COMPONENTS,
            None,
            {
                "type": "object",
                "description": "Pet plus extra",
                "properties": {
                    "id": {"type": "integer", "x-reference": "Pet"},
                    "name": {"type": "string", "x-reference": "Pet"},
                    "tag": {"type": "string", "x-reference": "ComposedPet"},
                },
                "required": ["name", "tag"],
                "x-reference": "ComposedPet",
            },
            id="allOf",
        ),
        pytest.param(
            PET_COMPONENTS["schemas"]["ComposedPet"],
            PET_COMPONENTS,
            None,
            {
                "type": "object",
                "description": "Pet plus extra",
                "properties": {
                    "id": {"type": "integer", "x-reference": "Pet"},
                    "name": {"type": "string", "x-reference": "Pet"},
                    "tag": {"type": "string"},
                },
                "required": ["name", "tag"],
                "x-reference": "Pet",
            },
            id="allOf-inline",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Owned"},
            {
                "schemas": {
                    **PET_COMPONENTS["schemas"],
                    "Owned": {
                        "type": "object",
                        "properties": {
                            "pet": {"$ref": "#/components/schemas/Pet"},
                            "note": {"type": "string"},
                        },
                    },
                },
            },
            None,
            {
                "type": "object",
                "properties": {
                    "pet": EXPANDED_PET,
                    "note": {"type": "string", "x-reference": "Owned"},
                },
                "x-reference": "Owned",
            },
            id="property-ref",
        ),
        pytest.param(
            {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}},
            PET_COMPONENTS,
            None,
            {"type": "array", "items": EXPANDED_PET},
            id="nested-ref",
        ),
        pytest.param(
            {"oneOf": [{"$ref": "#/components/schemas/Pet"}, {"type": "string"}]},
            PET_COMPONENTS,
            None,
            {"oneOf": [EXPANDED_PET, {"type": "string"}]},
            id="list",
        ),
        pytest.param(
            {
                "allOf": [
                    {"properties": {"name": {"type": "string"}, "id": {"type": "integer"}}, "required": ["name"]},
                    {"properties": {"name": {"description": "overridden"}}, "required": ["id"]},
                ]
            },
            {},
            None,
            {
                "properties": {
                    "name": {"description": "overridden"},
                    "id": {"type": "integer"},
                },
                "required": ["name", "id"],
            },
            id="allOf-replace",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/LoopA"},
            LOOP_COMPONENTS,
            None,
            {
                "type": "object",
                "properties": {
                    "fromB": {"type": "integer", "x-reference": "LoopB"},
                    "fromA": {"type": "string", "x-reference": "LoopA"},
                },
                "x-reference": "LoopA",
            },
            id="cycle",
        ),
        pytest.param(
            {"$ref": "#/components/schema/LoopC"},
            LOOP_COMPONENTS,
            None,
            {"$ref": "#/components/schema/LoopC"},
            id="bad-ref",
        ),
        pytest.param(
            {"$ref": "#/components/schema/LoopC"},
            LOOP_COMPONENTS,
            None,
            {"$ref": "#/components/schema/LoopC"},
            id="missing-ref",
        ),
        pytest.param(
            {"$ref": "#/components/schema/LoopA"},
            [],
            None,
            {"$ref": "#/components/schema/LoopA"},
            id="bad-component",
        ),
        pytest.param(
            {"properties": []},
            {},
            "foo",
            {"properties": []},
            id="prop-list",
        ),
        pytest.param(
            {"properties": {"name": []}},
            {},
            "foo",
            {"properties": {"name": []}},
            id="prop-value",
        ),
        pytest.param(
            {"properties": {"a": {"type": "string"}, "b":{"typer": "integer"}}},
            {},
            "/foo/Bar",
            {
                "properties":{
                    "a": {"type": "string", "x-reference": "Bar"},
                    "b":{"typer": "integer", "x-reference": "Bar"},
                },
            },
            id="name",
        ),
        pytest.param(
            {"type": "string", "enum": ["open", "closed"]},
            {},
            None,
            {"type": "string", "enum": ["open", "closed"]},
            id="inline-enum",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Status"},
            ENUM_COMPONENTS,
            None,
            EXPANDED_STATUS,
            id="enum-ref",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Status", "description": "Custom status"},
            ENUM_COMPONENTS,
            None,
            {**EXPANDED_STATUS, "description": "Custom status"},
            id="enum-ref-sibling",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/EmptyStatus"},
            ENUM_COMPONENTS,
            None,
            {"type": "string", "enum": [], "x-reference": "EmptyStatus"},
            id="empty-enum",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/BadStatus"},
            ENUM_COMPONENTS,
            None,
            {"type": "string", "enum": "open", "x-reference": "BadStatus"},
            id="non-list-enum",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/Pet"},
            ENUM_COMPONENTS,
            None,
            {
                "type": "object",
                "properties": {
                    "status": EXPANDED_STATUS,
                    "name": {"type": "string", "x-reference": "Pet"},
                },
                "x-reference": "Pet",
            },
            id="property-enum",
        ),
        pytest.param(
            {"type": "array", "items": {"$ref": "#/components/schemas/Status"}},
            ENUM_COMPONENTS,
            None,
            {"type": "array", "items": EXPANDED_STATUS},
            id="nested-enum",
        ),
        pytest.param(
            ENUM_COMPONENTS["schemas"]["LabeledStatus"],
            ENUM_COMPONENTS,
            None,
            {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "A labeled status",
                "x-reference": "Status",
                "x-enum": "Status",
            },
            id="allOf-enum",
        ),
        pytest.param(
            {"$ref": "#/components/schemas/LabeledStatus"},
            ENUM_COMPONENTS,
            None,
            {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "A labeled status",
                "x-reference": "LabeledStatus",
                "x-enum": "LabeledStatus",
            },
            id="allOf-enum-ref",
        ),
    ],
)
def test_expand_schema(
    schema: dict[str, Any] | None,
    components: dict[str, Any],
    name: str | None,
    expected: dict[str, Any],
) -> None:
    assert expected == expand_schema(schema, components, name)


def test_expand_schema_copies() -> None:
    components = {"schemas": {"Pet": {"type": "object", "properties": {"name": {"type": "string"}}}}}
    schema = {"$ref": "#/components/schemas/Pet", "description": "Custom"}
    expanded = expand_schema(schema, components)

    expanded["properties"]["name"]["type"] = "integer"
    assert components["schemas"]["Pet"]["properties"]["name"]["type"] == "string"
    assert schema == {"$ref": "#/components/schemas/Pet", "description": "Custom"}

