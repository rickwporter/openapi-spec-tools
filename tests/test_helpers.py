import pytest

from tests.helpers import deltas


@pytest.mark.parametrize(
    ["lhs", "rhs", "expected"],
    [
        pytest.param({}, {}, {}, id="empty"),
        pytest.param({"a": 1}, {"a": 1}, {}, id="equal"),
        pytest.param({"b": 1, "a": 1}, {"a": 1, "b": 1}, {}, id="key-order"),
        pytest.param({"a": 1}, {}, {"a": "missing"}, id="missing"),
        pytest.param({}, {"a": 1}, {"a": "added"}, id="added"),
        pytest.param({"a": 1, "b": 2}, {"b": 3, "c": 4}, {
            "a": "missing",
            "b": "2 != 3",
            "c": "added",
        }, id="mixed-keys"),
        pytest.param(
            {"a": {"b": 1, "c": 2}},
            {"a": {"b": 1, "d": 3}},
            {"a": {"c": "missing", "d": "added"}},
            id="nested-dict",
        ),
        pytest.param({"a": "left"}, {"a": "right"}, {"a": "'left' != 'right'"}, id="changed-scalar"),
        pytest.param({"a": None}, {"a": 1}, {"a": "None != 1"}, id="none"),
        pytest.param({"a": {"b": 1}}, {"a": [1]}, {"a": "{'b': 1} != [1]"}, id="type-mismatch"),
        pytest.param({"a": [1, 2]}, {"a": [1, 2]}, {}, id="equal-list"),
        pytest.param({"a": ["x", "y"]}, {"a": ["x", "z"]}, {"a": {"item[1]": "'y' != 'z'"}}, id="list-item"),
        pytest.param({"a": ["x", "y"]}, {"a": ["x"]}, {"a": {"item[1]": "missing"}}, id="list-missing"),
        pytest.param({"a": ["x"]}, {"a": ["x", "y"]}, {"a": {"item[1]": "added"}}, id="list-added"),
        pytest.param(
            {"a": [{"n": 1, "m": 2}, {"k": 1}]},
            {"a": [{"n": 1}, {"k": 1, "z": 9}, {"extra": True}]},
            {"a": {"item[0]": {"m": "missing"}, "item[1]": {"z": "added"}, "item[2]": "added"}},
            id="list-of-dicts",
        ),
        pytest.param(
            {"a": {"b": [{"c": [1, 2]}]}},
            {"a": {"b": [{"c": [1, 3, 4]}]}},
            {"a": {"b": {"item[0]": {"c": {"item[1]": "2 != 3", "item[2]": "added"}}}}},
            id="deep",
        ),
    ],
)
def test_deltas(lhs, rhs, expected):
    assert expected == deltas(lhs, rhs)
