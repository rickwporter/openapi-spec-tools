import pytest

from openapi_spec_tools.cli_gen._display import allowed
from openapi_spec_tools.cli_gen._display import remove


@pytest.mark.parametrize(
    ["data", "properties", "expected"],
    [
        pytest.param(None, ["foo"], None, id="None"),
        pytest.param({"foo": "bar"}, ["foo"], {"foo": "bar"}, id="all-exist"),
        pytest.param({"north": 1, "south": 2, "east": 3}, ["south"], {"south": 2}, id="filtered"),
        pytest.param({"north": 1, "south": 2, "east": 3}, ["west"], {"west": None}, id="missing"),
        pytest.param({"north": 1, "south": 2, "east": 3}, ["south", "north"], {"south": 2, "north": 1}, id="multiple"),
        pytest.param(
            [{"north": 1, "south": 2}, {"west": 1, "north": 3}, {"east": 1}],
            ["north"],
            [{"north": 1}, {"north": 3}, {"north": None}],
            id="list",
        ),
    ]
)
def test_allowed(data, properties, expected):
    assert expected == allowed(data, properties)


@pytest.mark.parametrize(
    ["data", "properties", "expected"],
    [
        pytest.param(None, ["foo"], None, id="None"),
        pytest.param({"foo": "bar"}, ["foo"], {}, id="simple"),
        pytest.param({"foo": "bar"}, ["bar"], {"foo": "bar"}, id="missing"),
        pytest.param({"sna": "foo", "foo": "bar", "bar": "sna"}, ["bar", "sna"], {"foo": "bar"}, id="multiple"),
        pytest.param(
            [{"north": 1, "south": 2}, {"west": 1, "north": 3}, {"east": 1}],
            ["north"],
            [{"south": 2}, {"west": 1}, {"east": 1}],
            id="list",
        ),
    ]
)
def test_remove(data, properties, expected):
    assert expected == remove(data, properties)

