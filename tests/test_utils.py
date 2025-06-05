from enum import Enum
from typing import Any

import pytest

from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import count_values
from openapi_spec_tools.utils import find_diffs
from openapi_spec_tools.utils import find_paths
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import map_content_types
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import model_filter
from openapi_spec_tools.utils import model_references
from openapi_spec_tools.utils import models_referenced_by
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required
from openapi_spec_tools.utils import short_ref

from .helpers import open_test_oas


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
        pytest.param({"my-list": set([1, 2, 3, 4, 5])}, 5, id="set-simple"),
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
        "schemas/Pets": set(["schemas/Pet"]),
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
    filtered = model_filter(models, set([model_name]))
    assert set(keys) == set(filtered)


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
    expected = set([
        "parameters/PageSize",
        "schemas/Pets",
        "schemas/Address",
        "schemas/Owner",
        "schemas/Species",
    ])
    assert expected.issubset(keys)


def test_map_operations() -> None:
    oas = open_test_oas("pet2.yaml")
    ops = map_operations(oas.get(OasField.PATHS))
    assert set(["listPets", "createPets", "showPetById", "deletePetById"]) == ops.keys()
    baseline_keys = set([
        OasField.OP_ID,
        OasField.RESPONSES,
        OasField.SUMMARY,
        OasField.TAGS,
        OasField.X_PATH,
        OasField.X_PATH_PARAMS,
        OasField.X_METHOD,
    ])

    expected_keys = baseline_keys | set([OasField.PARAMS])
    item = ops["listPets"]
    assert expected_keys == set(item.keys())
    assert item[OasField.OP_ID] == "listPets"
    assert item[OasField.X_PATH] == "/pets"
    assert item[OasField.X_METHOD] == "get"
    assert item[OasField.X_PATH_PARAMS] is None

    expected_keys = baseline_keys | set(["requestBody"])
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
        )
    ]
)
def test_set_nullable_not_required(filename: str, expected: dict[str, Any]) -> None:
    orig = open_test_oas(filename)
    updated = set_nullable_not_required(orig)
    diff = find_diffs(orig, updated)

    assert diff == expected


def test_schema_operations_filter_remove() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, remove=set(["deletePetById"]))

    diff = find_diffs(original, updated)
    assert diff == {
        OasField.PATHS.value: {"/pets/{petId}": {"delete": "removed"}},
        OasField.TAGS.value: "different lengths: 2 != 1"
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: deletePetById"):
        schema_operations_filter(updated, remove=set(["deletePetById", "listPets"]))

    third = schema_operations_filter(updated, remove=set(["listPets"]))
    diff = find_diffs(updated, third)
    assert diff == {
        OasField.COMPONENTS.value: {OasField.SCHEMAS: {"Pets": "removed"}},
        OasField.PATHS.value: {"/pets": {"get": "removed"}},
    }


def test_schema_operations_filter_allow() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, allow=set(["showPetById", "deletePetById"]))

    diff = find_diffs(original, updated)
    assert diff == {
        OasField.PATHS.value: {
            "/pets": "removed",
        },
        OasField.COMPONENTS.value: {OasField.SCHEMAS.value: {"Pets": "removed"}},
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: createPets"):
        schema_operations_filter(updated, allow=set(["createPets", "showPetById"]))

    third = schema_operations_filter(updated, allow=set(["deletePetById"]))
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
