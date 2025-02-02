from enum import Enum

import pytest

from oas_tools.constants import COMPONENTS
from oas_tools.constants import PARAMS
from oas_tools.constants import PATHS
from oas_tools.constants import PROPS
from oas_tools.constants import REQUIRED
from oas_tools.constants import SCHEMAS
from oas_tools.constants import TAGS
from oas_tools.utils import count_values
from oas_tools.utils import find_diffs
from oas_tools.utils import find_references

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
    path_data = oas.get(PATHS, {}).get(path)
    found = find_references(path_data)
    assert references == found


def test_find_diffs_pet_forward() -> None:
    orig = open_test_oas("pet.yaml")
    updated = open_test_oas("pet2.yaml")
    diff = find_diffs(orig, updated)
    assert diff[TAGS] == "added"
    assert diff[COMPONENTS][SCHEMAS] == {
        "Pet": {
            PROPS: {"owner": "added"},
            REQUIRED: "added owner",
        },
    }
    assert diff[PATHS] == {
        "/pets/{petId}": {
            PARAMS: "added",
            "delete": "added",
            "get": {PARAMS: "removed"},
        }
    }

    assert 6 == count_values(diff)

def test_find_diffs_pet_reverse() -> None:
    orig = open_test_oas("pet2.yaml")
    updated = open_test_oas("pet.yaml")
    diff = find_diffs(orig, updated)
    assert diff[TAGS] == "removed"
    assert diff[COMPONENTS][SCHEMAS] == {
        "Pet": {
            PROPS: {"owner": "removed"},
            REQUIRED: "removed owner",
        },
    }
    assert diff[PATHS] == {
        "/pets/{petId}": {
            PARAMS: "removed",
            "delete": "removed",
            "get": {PARAMS: "added"},
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
