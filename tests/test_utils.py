from enum import Enum

import pytest

from oas_tools.constants import Fields
from oas_tools.utils import count_values
from oas_tools.utils import find_diffs
from oas_tools.utils import find_references
from oas_tools.utils import map_operations

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
