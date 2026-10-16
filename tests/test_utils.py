from enum import Enum
from typing import Any

import pytest

from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import _flatten_collection
from openapi_spec_tools.utils import _flatten_collection_type
from openapi_spec_tools.utils import _or
from openapi_spec_tools.utils import count_values
from openapi_spec_tools.utils import find_diffs
from openapi_spec_tools.utils import find_paths
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import flatten_schema
from openapi_spec_tools.utils import map_content_types
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import model_filter
from openapi_spec_tools.utils import model_full_name
from openapi_spec_tools.utils import model_references
from openapi_spec_tools.utils import models_referenced_by
from openapi_spec_tools.utils import open_oas
from openapi_spec_tools.utils import reference_classname
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required
from openapi_spec_tools.utils import short_ref
from openapi_spec_tools.utils import unroll
from tests.helpers import asset_filename
from tests.helpers import open_test_oas


@pytest.mark.parametrize(
    ["args", "expected"],
    [
        pytest.param(["param", "config", "default"], "param", id="param"),
        pytest.param([None, "config", "default"], "config", id="config"),
        pytest.param([None, None, "default"], "default", id="default"),
        pytest.param(["", "config", "default"], "", id="empty-param"),
        pytest.param([0, 1, 2], 0, id="zero-param"),
        pytest.param([False, True, None], False, id="false-param"),
        pytest.param([], None, id="no-args"),
        pytest.param([None], None, id="none-arg"),
    ],
)
def test_default(args, expected):
    assert expected == _or(*args)


def test_default_raises():
    with pytest.raises(ValueError, match="missing"):
        _or(None, ValueError("missing"))

    assert "param" == _or("param", None, ValueError("missing"))


def test_open_oas() -> None:
    # check we get same values for JSON and YAML versions
    pet_yaml = open_oas(asset_filename("pet2.yaml"))
    pet_json = open_oas(asset_filename("pet2.json"))
    assert pet_yaml == pet_json

    with pytest.raises(FileNotFoundError):
        open_oas("no-such-file")


@pytest.mark.parametrize(
    ["full_name", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("#/components/sna", "sna", id="one"),
        pytest.param("#/components/sna/foo", "sna/foo", id="two"),
        pytest.param("/sna/foo/bar", "sna/foo/bar", id="no-component"),
    ]
)
def test_short_ref(full_name, expected) -> None:
    assert expected == short_ref(full_name)


@pytest.mark.parametrize(
    ["full_name", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("#/components/schemas/Xxx", "Xxx", id="schema"),
        pytest.param("#/components/parameters/PetId", "PetId", id="parameter"),
        pytest.param("schemas/Error", "Error", id="short"),
        pytest.param("AlreadyClass", "AlreadyClass", id="bare"),
    ],
)
def test_reference_classname(full_name, expected) -> None:
    assert expected == reference_classname(full_name)


@pytest.mark.parametrize(
    ["asset", "path", "references"],
    [
        pytest.param("pet.yaml", "/pets", {"schemas/Error", "schemas/Pet", "schemas/Pets"}, id="/pet"),
        pytest.param("pet.yaml", "/pets/{petId}", {"schemas/Error", "schemas/Pet"}, id="/pets/{petId}"),
        pytest.param("ct.yaml", "/api/schema/", set(), id="/api/schema"),
        pytest.param(
            "ct.yaml",
            "/api/v1/environments/",
            {"schemas/Environment", "schemas/EnvironmentCreate", "schemas/PaginatedEnvironmentList"},
            id="/api/v1/environments",
        )
    ],
)
def test_utils_find_path_references(asset, path, references) -> None:
    oas = open_test_oas(asset)
    path_data = oas.get(OasField.PATHS, {}).get(path)
    found = find_references(path_data)
    assert references == found


def test_find_diffs_pet_forward() -> None:
    orig = open_test_oas("pet.yaml")
    updated = open_test_oas("pet2.yaml")
    diff = find_diffs(orig, updated)
    assert diff[OasField.TAGS] == "added"
    assert diff[OasField.COMPONENTS][OasField.SCHEMAS] == {
        "Pet": {
            OasField.PROPS: {"owner": "added"},
            OasField.REQUIRED: "added owner",
        },
    }
    assert diff[OasField.PATHS] == {
        "/pets/{petId}": {
            OasField.PARAMS: "added",
            "delete": "added",
            "get": {OasField.PARAMS: "removed"},
        }
    }

    assert 6 == count_values(diff)

def test_find_diffs_pet_reverse() -> None:
    orig = open_test_oas("pet2.yaml")
    updated = open_test_oas("pet.yaml")
    diff = find_diffs(orig, updated)
    assert diff[OasField.TAGS] == "removed"
    assert diff[OasField.COMPONENTS][OasField.SCHEMAS] == {
        "Pet": {
            OasField.PROPS: {"owner": "removed"},
            OasField.REQUIRED: "removed owner",
        },
    }
    assert diff[OasField.PATHS] == {
        "/pets/{petId}": {
            OasField.PARAMS: "removed",
            "delete": "removed",
            "get": {OasField.PARAMS: "added"},
        }
    }

    assert 6 == count_values(diff)


def test_find_diffs_none_values() -> None:
    orig = {"a": None, "b": None, "c": "C"}
    updated = {"a": None, "b": "B", "c": None}
    diff = find_diffs(orig, updated)
    assert "a" not in diff
    assert diff["b"] == "original is None"
    assert diff["c"] == "updated is None"
    assert 2 == count_values(diff)


def test_find_diffs_long_text() -> None:
    orig = {"a": "this is text"}
    updated = {"a": "this is some long text that gets truncated to a shorter value"}
    diff = find_diffs(orig, updated)
    assert diff["a"] == "this is text != this is some ..."
    assert 1 == count_values(diff)

    diff = find_diffs(updated, orig)
    assert diff["a"] == "this is some ... != this is text"
    assert 1 == count_values(diff)


def test_find_diffs_list_dicts_length() -> None:
    orig = {"a": [{"x": "something"}, {"y": "else"}]}
    updated = {"a": [{"x": 1, "y": "text", "z": True}]}
    diff = find_diffs(orig, updated)
    assert diff["a"] == "different lengths: 2 != 1"
    assert 1 == count_values(diff)


def test_find_diffs_list_dicts_item() -> None:
    orig = {"a": [{"w": "something", "x": 1, "y": "text", "z": True}, {"a": 1}, {"b": 1, "c": 2}]}
    updated = {"a": [{"x": 1, "y": "text", "z": True}, {"a": 1}, {"b": 2, "c": 2, "d": 2}]}
    diff = find_diffs(orig, updated)
    assert diff["a[0]"] == {"w": "removed"}
    assert "a[1]" not in diff
    assert diff["a[2]"] == {"b": "1 != 2", "d": "added"}
    assert 3 == count_values(diff)


@pytest.mark.parametrize(
    ["obj", "count"],
    [
        pytest.param({}, 0, id="empty"),
        pytest.param({"a": 1, "b": True, "c": 3.0, "d": "result"}, 4, id="simple"),
        pytest.param({"deeper": {"a": 1, "b": True, "c": 3.0, "d": "result"}}, 4, id="nested"),
        pytest.param({"my-list": []}, 0, id="empty-list"),
        pytest.param({"my-list": ["a", 1, True, 2.5]}, 4, id="list-simple"),
        pytest.param({"my-list": [{"a": 1, "b": 2}, {"c": 2}]}, 3, id="list-dict"),
        pytest.param({"my-list": {1, 2, 3, 4, 5}}, 5, id="set-simple"),
    ],
)
def test_count_values_success(obj, count) -> None:
    assert count == count_values(obj)


def test_count_values_failure() -> None:
    class MyEnum(Enum):
        A = "a"
        B = "b"

    obj = {"a": "a", "b": MyEnum.A}
    with pytest.raises(ValueError) as error:
        count_values(obj)
    assert error.match("Unhandled type MyEnum for 'b'")


def test_model_references() -> None:
    oas = open_test_oas("pet2.yaml")
    models = map_models(oas.get(OasField.COMPONENTS, {}))
    expected = {
        "schemas/Pets": {"schemas/Pet"},
        "schemas/Pet": set(),
        "schemas/Error": set(),
    }
    assert expected == model_references(models)


@pytest.mark.parametrize(
    ["asset", "model_name", "keys"],
    [
        pytest.param("pet2.yaml", "schemas/Pets", ["schemas/Pets", "schemas/Pet"], id="multi"),
        pytest.param("pet2.yaml", "schemas/Pet", ["schemas/Pet"], id="single"),
    ],
)
def test_model_filter(
    asset: str,
    model_name: str,
    keys: list[str],
) -> None:
    schema = open_test_oas(asset)
    models = map_models(schema.get(OasField.COMPONENTS, {}))
    filtered = model_filter(models, {model_name})
    assert set(keys) == set(filtered)


@pytest.mark.parametrize(
    ["needle", "expected"],
    [
        pytest.param("", None, id="empty"),
        pytest.param("Error", "schemas/Error", id="partial"),
        pytest.param("schemas/Pets", "schemas/Pets", id="fullname"),
        # NOTE: does not test multiples in different sections
    ]
)
def test_model_full_name(needle, expected) -> None:
    schema = open_test_oas("pet2.yaml")
    models = map_models(schema.get(OasField.COMPONENTS, {}))
    assert expected == model_full_name(models, needle)


@pytest.mark.parametrize(
    ["asset", "model_name", "keys"],
    [
        pytest.param("pet2.yaml", "schemas/Pets", [], id="no-refs"),
        pytest.param("pet2.yaml", "schemas/Pet", ["schemas/Pets"], id="referenced"),
    ]
)
def test_models_referenced_by(
    asset: str,
    model_name: str,
    keys: list[str],
) -> None:
    schema = open_test_oas(asset)
    models = map_models(schema.get(OasField.COMPONENTS, {}))
    referenced_by = models_referenced_by(models, model_name)
    assert set(keys) == set(referenced_by)



def test_map_models() -> None:
    oas = open_test_oas("misc.yaml")
    models = map_models(oas.get(OasField.COMPONENTS))
    keys = models.keys()
    expected = {
        "parameters/PageSize",
        "schemas/Pets",
        "schemas/Address",
        "schemas/Owner",
        "schemas/Species",
    }
    assert expected.issubset(keys)


def test_map_operations() -> None:
    oas = open_test_oas("pet2.yaml")
    ops = map_operations(oas.get(OasField.PATHS))
    assert {"listPets", "createPets", "showPetById", "deletePetById"} == ops.keys()
    baseline_keys = {
        OasField.OP_ID,
        OasField.RESPONSES,
        OasField.SUMMARY,
        OasField.TAGS,
        OasField.X_PATH,
        OasField.X_PATH_PARAMS,
        OasField.X_METHOD,
    }

    expected_keys = baseline_keys | {OasField.PARAMS}
    item = ops["listPets"]
    assert expected_keys == set(item.keys())
    assert item[OasField.OP_ID] == "listPets"
    assert item[OasField.X_PATH] == "/pets"
    assert item[OasField.X_METHOD] == "get"
    assert item[OasField.X_PATH_PARAMS] is None

    expected_keys = baseline_keys | {"requestBody"}
    item = ops["createPets"]
    assert expected_keys == set(item.keys())
    assert item[OasField.OP_ID] == "createPets"
    assert item[OasField.X_PATH] == "/pets"
    assert item[OasField.X_METHOD] == "post"
    assert item[OasField.X_PATH_PARAMS] is None

    expected_keys = baseline_keys
    item = ops["deletePetById"]
    assert expected_keys == set(item.keys())
    assert item[OasField.OP_ID] == "deletePetById"
    assert item[OasField.X_PATH] == "/pets/{petId}"
    assert item[OasField.X_METHOD] == "delete"
    assert item[OasField.X_PATH_PARAMS] == [
        {
            OasField.NAME: "petId",
            OasField.IN: "path",
            OasField.REQUIRED: True,
            OasField.DESCRIPTION: "The id of the pet to retrieve",
            OasField.SCHEMA: {OasField.TYPE: "string"},
        },
    ]

    expected_keys = baseline_keys
    item = ops["showPetById"]
    assert expected_keys == set(item.keys())
    assert item[OasField.OP_ID] == "showPetById"
    assert item[OasField.X_PATH] == "/pets/{petId}"
    assert item[OasField.X_METHOD] == "get"
    assert item[OasField.X_PATH_PARAMS] == [
        {
            OasField.NAME: "petId",
            OasField.IN: "path",
            OasField.REQUIRED: True,
            OasField.DESCRIPTION: "The id of the pet to retrieve",
            OasField.SCHEMA: {OasField.TYPE: "string"},
        },
    ]

    # make sure this was non-destructive
    reread = open_test_oas("pet2.yaml")
    delta = find_diffs(oas, reread)
    assert not delta

@pytest.mark.parametrize(
    ["filename", "search", "subpaths", "expected"],
    [
        pytest.param("pet2.yaml", "/pets", False, ["/pets"], id="pets"),
        pytest.param("pet2.yaml", "/pets", True, ["/pets", "/pets/{petId}"], id="pets-subpath"),
        pytest.param("pet2.yaml", "/pets/{petId}", True, ["/pets/{petId}"], id="petId"),
        pytest.param("pet2.yaml", "/pets/", False, ["/pets"], id="trailing-slash"),
        pytest.param("pet2.yaml", "/pETs", True, ["/pets", "/pets/{petId}"], id="case-insensitive"),
    ],
)
def test_find_paths(filename, search, subpaths, expected) -> None:
    oas = open_test_oas(filename)
    actual = find_paths(oas.get(OasField.PATHS), search, subpaths)
    assert set(expected) == set(actual.keys())



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


def path_tag_count(schema: dict[str, Any]) -> int:
    tag_count = 0

    for path_data in schema.get(OasField.PATHS, {}).values():
        for op_data in path_data.values():
            # parameters field is a list, instead of a dict
            if not isinstance(op_data, dict):
                continue
            tags = op_data.get(OasField.TAGS, [])
            tag_count += len(tags)

    return tag_count


def test_remove_schema_tags_full() -> None:
    orig = open_test_oas("pet2.yaml")
    orig_count = path_tag_count(orig)
    assert 0 != orig_count
    assert OasField.TAGS in orig

    updated = remove_schema_tags(orig)
    up_count = path_tag_count(updated)
    assert 0 == up_count
    assert OasField.TAGS not in updated

    diff = find_diffs(orig, updated)
    assert diff == {
        OasField.PATHS.value: {
            '/pets': {
                "get": {OasField.TAGS.value: "removed"},
                "post": {OasField.TAGS.value: "removed"},
            },
            "/pets/{petId}": {
                "delete": {OasField.TAGS.value: "removed"},
                "get": {OasField.TAGS.value: "removed"}
            }
        },
        OasField.TAGS.value: "removed",
    }


def test_remove_schema_tags_no_top() -> None:
    orig = open_test_oas("ct.yaml")
    orig_count = path_tag_count(orig)
    assert 0 != orig_count
    assert OasField.TAGS not in orig

    updated = remove_schema_tags(orig)
    up_count = path_tag_count(updated)
    assert 0 == up_count
    assert OasField.TAGS not in updated

    diff = find_diffs(orig, updated)
    assert 191 == count_values(diff)


@pytest.mark.parametrize(
    ["filename", "expected"],
    [
        pytest.param(
            "pet2.yaml",
            {
                OasField.COMPONENTS.value: {
                    OasField.SCHEMAS.value: {'Pet' : {OasField.REQUIRED.value: "removed owner"}},
                },
            },
            id="pet2",
        ),
        pytest.param(
            "oas31.yaml",
            {
                OasField.COMPONENTS.value: {
                    OasField.SCHEMAS.value: {
                        'Service': {OasField.REQUIRED.value: "removed consumers, websites"},
                    },
                },
            },
            id="oas31"
        ),
        pytest.param(
            "misc2.yaml",
            {
                OasField.COMPONENTS.value: {
                    OasField.SCHEMAS.value: {
                        'Foo': {'required': 'removed'}
                    },
                },
            },
            id="no-required"
        ),
    ]
)
def test_set_nullable_not_required(filename: str, expected: dict[str, Any]) -> None:
    orig = open_test_oas(filename)
    updated = set_nullable_not_required(orig)
    diff = find_diffs(orig, updated)

    assert diff == expected


def test_schema_operations_filter_remove() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, remove={"deletePetById"})

    diff = find_diffs(original, updated)
    assert diff == {
        OasField.PATHS.value: {"/pets/{petId}": {"delete": "removed"}},
        OasField.TAGS.value: "different lengths: 2 != 1"
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: deletePetById"):
        schema_operations_filter(updated, remove={"deletePetById", "listPets"})

    third = schema_operations_filter(updated, remove={"listPets"})
    diff = find_diffs(updated, third)
    assert diff == {
        OasField.COMPONENTS.value: {OasField.SCHEMAS: {"Pets": "removed"}},
        OasField.PATHS.value: {"/pets": {"get": "removed"}},
    }


def test_unroll_cycle() -> None:
    full_set = {"a": {"b"}, "b": {"a", "c"}, "c": set()}
    assert {"a", "b", "c"} == unroll(full_set, {"a"})


def test_schema_operations_filter_remove_tags() -> None:
    original = open_test_oas("misc2.yaml")
    updated = schema_operations_filter(original, remove={"deleteSomethingElse"})
    diff = find_diffs(original, updated)
    assert diff == {
        OasField.COMPONENTS.value: {OasField.SCHEMAS: {"Foo": "removed"}},
        OasField.PATHS.value: {"/something/else": {"delete": "removed"}},
        OasField.TAGS.value: "removed",
    }


def test_schema_operations_filter_allow() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, allow={"showPetById", "deletePetById"})

    diff = find_diffs(original, updated)
    assert diff == {
        OasField.PATHS.value: {
            "/pets": "removed",
        },
        OasField.COMPONENTS.value: {OasField.SCHEMAS.value: {"Pets": "removed"}},
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: createPets"):
        schema_operations_filter(updated, allow={"createPets", "showPetById"})

    third = schema_operations_filter(updated, allow={"deletePetById"})
    diff = find_diffs(updated, third)
    assert diff == {
        OasField.PATHS.value: {"/pets/{petId}": {"get": "removed"}},
        OasField.TAGS.value: "different lengths: 2 != 1",
        OasField.COMPONENTS.value: {OasField.SCHEMAS.value: {"Pet": "removed"}},
    }


def test_map_content_types():
    schema = open_test_oas("pet2.yaml")
    result = map_content_types(schema)
    expected = {'createPets', 'deletePetById', 'showPetById', 'listPets'}
    assert expected == result['application/json']


def test_remove_property():
    original = {
        "a": "b",
        "b": "c",
        "c": {"d": "e"},  # empty dict is removed
        "d": None,
        "e": {},
        "f": [
            None,
            "a",
            {"d": 1},  # keep empty dict's in list to preserve order/size
            {"d": 2, "e": True},
        ],
        "g": [],
        "h": None,
    }
    expected = {
        "a": "b",
        "b": "c",
        "e": {},
        "f": [None, "a", {}, {"e": True}],
        "g": [],
        "h": None,
    }
    assert expected == remove_property(original, "d")
