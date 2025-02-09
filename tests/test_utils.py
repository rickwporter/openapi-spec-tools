from enum import Enum
from typing import Any

import pytest

from oas_tools.constants import Fields
from oas_tools.utils import count_values
from oas_tools.utils import find_diffs
from oas_tools.utils import find_paths
from oas_tools.utils import find_references
from oas_tools.utils import map_operations
from oas_tools.utils import model_filter
from oas_tools.utils import model_references
from oas_tools.utils import remove_schema_tags
from oas_tools.utils import schema_operations_filter
from oas_tools.utils import set_nullable_not_required

from .helpers import open_test_oas


@pytest.mark.parametrize(
    ["asset", "path", "references"],
    [
        pytest.param("pet.yaml", "/pets", {"Error", "Pet", "Pets"}, id="/pet"),
        pytest.param("pet.yaml", "/pets/{petId}", {"Error", "Pet"}, id="/pets/{petId}"),
        pytest.param("ct.yaml", "/api/schema/", set(), id="/api/schema"),
        pytest.param(
            "ct.yaml",
            "/api/v1/environments/",
            {"Environment", "EnvironmentCreate", "PaginatedEnvironmentList"},
            id="/api/v1/environments",
        )
    ],
)
def test_utils_find_path_references(asset, path, references) -> None:
    oas = open_test_oas(asset)
    path_data = oas.get(Fields.PATHS, {}).get(path)
    found = find_references(path_data)
    assert references == found


def test_find_diffs_pet_forward() -> None:
    orig = open_test_oas("pet.yaml")
    updated = open_test_oas("pet2.yaml")
    diff = find_diffs(orig, updated)
    assert diff[Fields.TAGS] == "added"
    assert diff[Fields.COMPONENTS][Fields.SCHEMAS] == {
        "Pet": {
            Fields.PROPS: {"owner": "added"},
            Fields.REQUIRED: "added owner",
        },
    }
    assert diff[Fields.PATHS] == {
        "/pets/{petId}": {
            Fields.PARAMS: "added",
            "delete": "added",
            "get": {Fields.PARAMS: "removed"},
        }
    }

    assert 6 == count_values(diff)

def test_find_diffs_pet_reverse() -> None:
    orig = open_test_oas("pet2.yaml")
    updated = open_test_oas("pet.yaml")
    diff = find_diffs(orig, updated)
    assert diff[Fields.TAGS] == "removed"
    assert diff[Fields.COMPONENTS][Fields.SCHEMAS] == {
        "Pet": {
            Fields.PROPS: {"owner": "removed"},
            Fields.REQUIRED: "removed owner",
        },
    }
    assert diff[Fields.PATHS] == {
        "/pets/{petId}": {
            Fields.PARAMS: "removed",
            "delete": "removed",
            "get": {Fields.PARAMS: "added"},
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
    models = oas.get(Fields.COMPONENTS, {}).get(Fields.SCHEMAS, {})
    expected = {
        "Pets": set(["Pet"]),
        "Pet": set(),
        "Error": set(),
    }
    assert expected == model_references(models)


@pytest.mark.parametrize(
    ["asset", "model_name", "keys"],
    [
        pytest.param("pet2.yaml", "Pets", ["Pets", "Pet"]),
        pytest.param("pet2.yaml", "Pet", ["Pet"]),
    ],
)
def test_model_filter(
    asset: str,
    model_name: str,
    keys: list[str],
) -> None:
    schema = open_test_oas(asset)
    models = schema.get(Fields.COMPONENTS, {}).get(Fields.SCHEMAS, {})
    filtered = model_filter(models, set([model_name]))
    assert set(keys) == set(filtered)


def test_map_operations() -> None:
    oas = open_test_oas("pet2.yaml")
    ops = map_operations(oas.get(Fields.PATHS))
    assert set(["listPets", "createPets", "showPetById", "deletePetById"]) == ops.keys()
    baseline_keys = set([
        Fields.OP_ID,
        Fields.RESPONSES,
        Fields.SUMMARY,
        Fields.TAGS,
        Fields.X_PATH,
        Fields.X_PATH_PARAMS,
        Fields.X_METHOD,
    ])

    expected_keys = baseline_keys | set([Fields.PARAMS])
    item = ops["listPets"]
    assert expected_keys == set(item.keys())
    assert item[Fields.OP_ID] == "listPets"
    assert item[Fields.X_PATH] == "/pets"
    assert item[Fields.X_METHOD] == "get"
    assert item[Fields.X_PATH_PARAMS] is None

    expected_keys = baseline_keys | set(["requestBody"])
    item = ops["createPets"]
    assert expected_keys == set(item.keys())
    assert item[Fields.OP_ID] == "createPets"
    assert item[Fields.X_PATH] == "/pets"
    assert item[Fields.X_METHOD] == "post"
    assert item[Fields.X_PATH_PARAMS] is None

    expected_keys = baseline_keys
    item = ops["deletePetById"]
    assert expected_keys == set(item.keys())
    assert item[Fields.OP_ID] == "deletePetById"
    assert item[Fields.X_PATH] == "/pets/{petId}"
    assert item[Fields.X_METHOD] == "delete"
    assert item[Fields.X_PATH_PARAMS] == [
        {
            Fields.NAME: "petId",
            Fields.IN: "path",
            Fields.REQUIRED: True,
            Fields.DESCRIPTION: "The id of the pet to retrieve",
            Fields.SCHEMA: {Fields.TYPE: "string"},
        },
    ]

    expected_keys = baseline_keys
    item = ops["showPetById"]
    assert expected_keys == set(item.keys())
    assert item[Fields.OP_ID] == "showPetById"
    assert item[Fields.X_PATH] == "/pets/{petId}"
    assert item[Fields.X_METHOD] == "get"
    assert item[Fields.X_PATH_PARAMS] == [
        {
            Fields.NAME: "petId",
            Fields.IN: "path",
            Fields.REQUIRED: True,
            Fields.DESCRIPTION: "The id of the pet to retrieve",
            Fields.SCHEMA: {Fields.TYPE: "string"},
        },
    ]


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
    actual = find_paths(oas.get(Fields.PATHS), search, subpaths)
    assert set(expected) == set(actual.keys())


def path_tag_count(schema: dict[str, Any]) -> int:
    tag_count = 0

    for path_data in schema.get(Fields.PATHS, {}).values():
        for op_data in path_data.values():
            # parameters field is a list, instead of a dict
            if not isinstance(op_data, dict):
                continue
            tags = op_data.get(Fields.TAGS, [])
            tag_count += len(tags)

    return tag_count


def test_remove_schema_tags_full() -> None:
    orig = open_test_oas("pet2.yaml")
    orig_count = path_tag_count(orig)
    assert 0 != orig_count
    assert Fields.TAGS in orig

    updated = remove_schema_tags(orig)
    up_count = path_tag_count(updated)
    assert 0 == up_count
    assert Fields.TAGS not in updated

    diff = find_diffs(orig, updated)
    assert diff == {
        Fields.PATHS.value: {
            '/pets': {
                "get": {Fields.TAGS.value: "removed"},
                "post": {Fields.TAGS.value: "removed"},
            },
            "/pets/{petId}": {
                "delete": {Fields.TAGS.value: "removed"},
                "get": {Fields.TAGS.value: "removed"}
            }
        },
        Fields.TAGS.value: "removed",
    }


def test_remove_schema_tags_no_top() -> None:
    orig = open_test_oas("ct.yaml")
    orig_count = path_tag_count(orig)
    assert 0 != orig_count
    assert Fields.TAGS not in orig

    updated = remove_schema_tags(orig)
    up_count = path_tag_count(updated)
    assert 0 == up_count
    assert Fields.TAGS not in updated

    diff = find_diffs(orig, updated)
    assert 191 == count_values(diff)


def test_set_nullable_not_required() -> None:
    orig = open_test_oas("pet2.yaml")
    updated = set_nullable_not_required(orig)
    diff = find_diffs(orig, updated)

    assert diff == {
        Fields.COMPONENTS.value: {
            Fields.SCHEMAS.value: {'Pet' : {Fields.REQUIRED.value: "removed owner"}},
        }
    }


def test_schema_operations_filter_remove() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, remove=set(["deletePetById"]))

    diff = find_diffs(original, updated)
    assert diff == {
        Fields.PATHS.value: {"/pets/{petId}": {"delete": "removed"}},
        Fields.TAGS.value: "different lengths: 2 != 1"
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: deletePetById"):
        schema_operations_filter(updated, remove=set(["deletePetById", "listPets"]))

    third = schema_operations_filter(updated, remove=set(["listPets"]))
    diff = find_diffs(updated, third)
    assert diff == {
        Fields.COMPONENTS.value: {Fields.SCHEMAS: {"Pets": "removed"}},
        Fields.PATHS.value: {"/pets": {"get": "removed"}},
    }


def test_schema_operations_filter_allow() -> None:
    original = open_test_oas("pet2.yaml")
    updated = schema_operations_filter(original, allow=set(["showPetById", "deletePetById"]))

    diff = find_diffs(original, updated)
    assert diff == {
        Fields.PATHS.value: {
            "/pets": "removed",
        },
        Fields.COMPONENTS.value: {Fields.SCHEMAS.value: {"Pets": "removed"}},
    }

    # make sure we throw an exception when operation is not found
    with pytest.raises(ValueError, match="schema is missing: createPets"):
        schema_operations_filter(updated, allow=set(["createPets", "showPetById"]))

    third = schema_operations_filter(updated, allow=set(["deletePetById"]))
    diff = find_diffs(updated, third)
    assert diff == {
        Fields.PATHS.value: {"/pets/{petId}": {"get": "removed"}},
        Fields.TAGS.value: "different lengths: 2 != 1",
        Fields.COMPONENTS.value: {Fields.SCHEMAS.value: {"Pet": "removed"}},
    }
