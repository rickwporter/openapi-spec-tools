from typing import Any

import pytest

from openapi_spec_tools.flatten import _flatten_collection
from openapi_spec_tools.flatten import _flatten_collection_type
from openapi_spec_tools.flatten import flatten_schema


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        pytest.param(None, {}, id="none"),
        pytest.param({}, {}, id="empty"),
        pytest.param(
            {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            {
                "type": "object",
                "properties": {"name": {"type": "string", "x-field": "name", "required": True}},
                "required": ["name"],
            },
            id="plain",
        ),
        pytest.param(
            {
                "type": "object",
                "description": "root",
                "properties": {
                    "id": {"type": "integer"},
                    "owner": {
                        "type": "object",
                        "description": "the owner",
                        "properties": {"name": {"type": "string", "description": "owner name"}},
                    },
                },
            },
            {
                "type": "object",
                "description": "root",
                "properties": {
                    "id": {"type": "integer", "x-field": "id", "required": False},
                    "owner.name": {
                        "type": "string",
                        "description": "owner name",
                        "x-parents": ["owner"],
                        "x-field": "name",
                        "required": False,
                    },
                },
            },
            id="one-level",
        ),
        pytest.param(
            {
                "type": "object",
                "required": ["id", "owner", "missing"],
                "properties": {
                    "id": {"type": "integer"},
                    "owner": {
                        "type": "object",
                        "required": ["name", "home"],
                        "properties": {
                            "name": {"type": "string"},
                            "nickname": {"type": "string"},
                            "home": {
                                "type": "object",
                                "required": ["street"],
                                "properties": {
                                    "street": {"type": "string"},
                                    "city": {"type": "string"},
                                },
                            },
                        },
                    },
                    "tag": {"type": "string"},
                },
            },
            {
                "type": "object",
                "required": ["id", "owner.name", "owner.home.street", "missing"],
                "properties": {
                    "id": {"type": "integer", "x-field": "id", "required": True},
                    "owner.name": {"type": "string", "x-parents": ["owner"], "x-field": "name", "required": True},
                    "owner.nickname": {
                        "type": "string",
                        "x-parents": ["owner"],
                        "x-field": "nickname",
                        "required": False,
                    },
                    "owner.home.street": {
                        "type": "string",
                        "x-parents": ["owner", "home"],
                        "x-field": "street",
                        "required": True,
                    },
                    "owner.home.city": {
                        "type": "string",
                        "x-parents": ["owner", "home"],
                        "x-field": "city",
                        "required": False,
                    },
                    "tag": {"type": "string", "x-field": "tag", "required": False},
                },
            },
            id="nested-required",
        ),
        pytest.param(
            {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "integer"},
                    "owner": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {"name": {"type": "string"}},
                    },
                },
            },
            {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "integer", "x-field": "id", "required": True},
                    "owner.name": {"type": "string", "x-parents": ["owner"], "x-field": "name", "required": False},
                },
            },
            id="optional-parent",
        ),
        pytest.param(
            {
                "type": "object",
                "required": ["owner"],
                "properties": {
                    "owner": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                },
            },
            {
                "type": "object",
                "required": [],
                "properties": {
                    "owner.name": {"type": "string", "x-parents": ["owner"], "x-field": "name", "required": False},
                },
            },
            id="required-parent-without-required-children",
        ),
        pytest.param(
            {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["meta"],
                            "properties": {
                                "meta": {
                                    "type": "object",
                                    "required": ["color"],
                                    "properties": {"color": {"type": "string"}},
                                }
                            },
                        },
                    }
                },
            },
            {
                "type": "object",
                "properties": {
                    "tags.meta.color": {
                        "type": "string",
                        "x-parents": ["tags", "meta"],
                        "x-field": "color",
                        "x-forced-single": True,
                        "required": False,
                    }
                },
            },
            id="items",
        ),
        pytest.param(
            {
                "type": "object",
                "required": ["tags"],
                "properties": {
                    "id": {"type": "integer"},
                    "tags": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                                "color": {"type": "string"},
                                "home": {
                                    "type": "object",
                                    "required": ["city"],
                                    "properties": {
                                        "city": {"type": "string"},
                                        "street": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
            },
            {
                "type": "object",
                "required": ["tags.name"],
                "properties": {
                    "id": {"type": "integer", "x-field": "id", "required": False},
                    "tags.name": {
                        "type": "string",
                        "x-field": "name",
                        "x-parents": ["tags"],
                        "x-forced-single": True,
                        "required": True,
                    },
                    "tags.color": {
                        "type": "string",
                        "x-field": "color",
                        "x-parents": ["tags"],
                        "x-forced-single": True,
                        "required": False,
                    },
                    "tags.home.city": {
                        "type": "string",
                        "x-field": "city",
                        "x-parents": ["tags", "home"],
                        "x-forced-single": True,
                        "required": False,
                    },
                    "tags.home.street": {
                        "type": "string",
                        "x-field": "street",
                        "x-parents": ["tags", "home"],
                        "x-forced-single": True,
                        "required": False,
                    },
                    "labels": {
                        "type": "string",
                        "x-collection": "array",
                        "x-field": "labels",
                        "required": False,
                    },
                },
            },
            id="complex-collection",
        ),
        pytest.param(
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "description": "Names", "items": {"type": "string"}},
                    "flags": {"type": "array", "items": {"type": "boolean"}},
                    "scores": {"type": "array", "items": {"type": "number", "format": "double"}},
                    "ids": {"type": ["array", "null"], "items": {"type": "integer", "format": "int64"}},
                },
            },
            {
                "type": "object",
                "properties": {
                    "labels": {
                        "type": "string",
                        "description": "Names",
                        "x-collection": "array",
                        "x-field": "labels",
                        "required": False,
                    },
                    "flags": {
                        "type": "boolean",
                        "x-collection": "array",
                        "x-field": "flags",
                        "required": False,
                    },
                    "scores": {
                        "type": "number",
                        "format": "double",
                        "x-collection": "array",
                        "x-field": "scores",
                        "required": False,
                    },
                    "ids": {
                        "type": "integer",
                        "format": "int64",
                        "x-collection": "array",
                        "x-field": "ids",
                        "required": False,
                    },
                },
            },
            id="simple-array",
        ),
        pytest.param(
            {
                "description": "A pet",
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "home": {"type": "object", "properties": {"city": {"type": "string"}}},
                        },
                    },
                    {"type": "string"},
                ],
            },
            {
                "description": "A pet",
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "x-field": "name", "required": True},
                    "home.city": {
                        "type": "string",
                        "x-field": "city",
                        "x-parents": ["home"],
                        "required": False,
                    },
                },
            },
            id="oneOf",
        ),
        pytest.param(
            {
                "type": "object",
                "properties": {
                    "status": {
                        "description": "Current status",
                        "nullable": True,
                        "oneOf": [
                            {"type": "string", "enum": ["open", "closed"]},
                            {"type": "integer"},
                        ],
                    },
                    "label": {
                        "description": "outer",
                        "oneOf": [{"type": "string", "description": "inner"}],
                    },
                },
            },
            {
                "type": "object",
                "properties": {
                    "status": {
                        "description": "Current status",
                        "nullable": True,
                        "type": "string",
                        "enum": ["open", "closed"],
                        "x-field": "status",
                        "required": False,
                    },
                    "label": {
                        "description": "inner",
                        "type": "string",
                        "x-field": "label",
                        "required": False,
                    },
                },
            },
            id="oneOf-property",
        ),
        pytest.param(
            {
                "type": "object",
                "properties": {
                    "pet": {
                        "oneOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "color": {"type": "string"},
                                    },
                                },
                            },
                            {"type": "string"},
                        ]
                    }
                },
            },
            {
                "type": "object",
                "properties": {
                    "pet.name": {
                        "type": "string",
                        "x-field": "name",
                        "x-parents": ["pet"],
                        "x-forced-single": True,
                        "required": False,
                    },
                    "pet.color": {
                        "type": "string",
                        "x-field": "color",
                        "x-parents": ["pet"],
                        "x-forced-single": True,
                        "required": False,
                    },
                },
            },
            id="oneOf-collection",
        ),
        pytest.param({"oneOf": []}, {"oneOf": []}, id="empty-oneOf"),
        pytest.param(
            {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {
                            "home": {"type": "object", "properties": {"city": {"type": "string"}}}
                        },
                    }
                ]
            },
            {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {
                            "home.city": {
                                "type": "string",
                                "x-parents": ["home"],
                                "x-field": "city",
                                "required": False,
                            },
                        },
                    }
                ]
            },
            id="allOf",
        ),
        pytest.param(
            {
                "type": "object",
                "properties": {
                    "extra": {"type": "object", "additionalProperties": {"type": "string"}},
                    "empty": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "object",
                "properties": {
                    "extra": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "x-field": "extra",
                        "required": False,
                    },
                    "empty": {"type": "object", "properties": {}, "x-field": "empty", "required": False},
                },
            },
            id="no-cascaded-properties",
        ),
        pytest.param(
            {
                "properties": {
                    "owner": {
                        "properties": {
                            "home.city": {"type": "string", "x-parents": ["home"]},
                            "name": "bad",
                        }
                    }
                }
            },
            {
                "properties": {
                    "owner.home.city": {
                        "type": "string",
                        "x-parents": ["owner", "home"],
                        "x-field": "city",
                        "required": False,
                    },
                    "owner.name": "bad",
                }
            },
            id="existing-parents",
        ),
        pytest.param(
            {"properties": {"owner": {"properties": {"city": {"type": "string", "x-parents": "home"}}}}},
            {
                "properties": {
                    "owner.city": {
                        "type": "string",
                        "x-parents": ["owner", "home"],
                        "x-field": "city",
                        "required": False,
                    },
                },
            },
            id="scalar-parents",
        ),
        pytest.param(
            {
                "$ref": "#/components/schemas/Owner",
                "x-reference": "Owner",
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "home": {
                        "$ref": "#/components/schemas/Address",
                        "type": "object",
                        "properties": {
                            "street": {"type": "string"},
                            "zip_code": {"$ref": "#/components/schemas/ZipCode", "type": "string"},
                        },
                    },
                },
            },
            {
                "$ref": "#/components/schemas/Owner",
                "x-reference": "Owner",
                "type": "object",
                "properties": {
                    "name": {"type": "string", "x-field": "name", "x-reference": "Owner", "required": False},
                    "home.street": {
                        "type": "string",
                        "x-field": "street",
                        "x-parents": ["home"],
                        "x-reference": "Address",
                        "required": False,
                    },
                    "home.zip_code": {
                        "$ref": "#/components/schemas/ZipCode",
                        "type": "string",
                        "x-field": "zip_code",
                        "x-parents": ["home"],
                        "x-reference": "ZipCode",
                        "required": False,
                    },
                },
            },
            id="lowest-ref",
        ),
        pytest.param(
            {
                "x-reference": "Owner",
                "properties": {
                    "home": {"type": "object", "properties": {"city": {"type": "string"}}},
                },
            },
            {
                "x-reference": "Owner",
                "properties": {
                    "home.city": {
                        "type": "string",
                        "x-field": "city",
                        "x-parents": ["home"],
                        "x-reference": "Owner",
                        "required": False,
                    },
                },
            },
            id="inherited-ref",
        ),
    ],
)
def test_flatten_schema(schema: dict[str, Any] | None, expected: dict[str, Any]) -> None:
    assert expected == flatten_schema(schema)


def test_flatten_schema_copies() -> None:
    schema = {
        "type": "object",
        "required": ["owner"],
        "properties": {
            "owner": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
        },
    }
    original = {
        "type": "object",
        "required": ["owner"],
        "properties": {
            "owner": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
        },
    }
    flattened = flatten_schema(schema)

    flattened["properties"]["owner.name"]["type"] = "integer"
    flattened["required"].append("extra")
    assert schema == original


@pytest.mark.parametrize(
    ["model", "expected"],
    [
        pytest.param({"type": "array"}, "array", id="simple"),
        pytest.param({"type": "number"}, None, id="type-str"),
        pytest.param({"type": {"array"}}, None, id="type-set"),
        pytest.param({"type": ["null", "array"]}, "array", id="list-null"),
        pytest.param({"type": ["foo", "array"]}, None, id="list-unknown"),
    ]
)
def test__flatten_collection_type(model: dict[str, Any], expected: str | None) -> None:
    assert expected == _flatten_collection_type(model)


@pytest.mark.parametrize(
    ["model", "updated", "expected"],
    [
        pytest.param({}, {}, False, id="empty"),
        pytest.param({"type": "string"}, {"type": "string"}, False, id="no-update"),
        pytest.param({"type": "array"}, {"type": "array"}, False, id="no-item"),
        pytest.param(
            {"type": "array", "items": ["string"]},
            {"type": "array", "items": ["string"]},
            False,
            id="non-dict-items",
        ),
        pytest.param(
            {"type": "array", "items": {"type": "string"}, "description": "simple"},
            {"type": "string", "x-collection": "array", "description": "simple"},
            True,
            id="simple",
        ),
    ]
)
def test__flatten_collection(model: dict[str, Any], updated: dict[str, Any], expected: bool) -> None:
    assert expected == _flatten_collection(model)
    assert model == updated


