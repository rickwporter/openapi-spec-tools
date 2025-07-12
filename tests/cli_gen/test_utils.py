import pytest

from openapi_spec_tools.cli_gen.utils import is_case_sensitive
from openapi_spec_tools.cli_gen.utils import maybe_quoted
from openapi_spec_tools.cli_gen.utils import prepend
from openapi_spec_tools.cli_gen.utils import replace_special
from openapi_spec_tools.cli_gen.utils import set_missing
from openapi_spec_tools.cli_gen.utils import shallow
from openapi_spec_tools.cli_gen.utils import to_camel_case
from openapi_spec_tools.cli_gen.utils import to_snake_case


@pytest.mark.parametrize(
    ["text", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("foo", "foo", id="unchanged"),
        pytest.param("fooBar", "foo_bar", id="simple"),
        pytest.param("snaFooBar", "sna_foo_bar", id="two"),
        pytest.param("SNAFoo", "sna_foo", id="multi-caps"),
        pytest.param("sna_foo", "sna_foo", id="snake"),
        pytest.param("SnaFooBar123_MORE", "sna_foo_bar123_more", id="numbers"),
    ]
)
def test_snake_case(text, expected):
    assert expected == to_snake_case(text)


@pytest.mark.parametrize(
    ["text", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("foo", "foo", id="unchanged"),
        pytest.param("foo_bar", "fooBar", id="simple"),
        pytest.param("FooBar", "FooBar", id="unchanged"),
        pytest.param("sna_foo_bar", "snaFooBar", id="two"),
        pytest.param("snaFoo", "snaFoo", id="camel"),
        pytest.param("sna_foo_bar123_more", "snaFooBar123More", id="numbers"),
    ]
)
def test_camel_case(text, expected):
    assert expected == to_camel_case(text)


@pytest.mark.parametrize(
    ["item", "expected"],
    [
        pytest.param("", '""', id="empty"),
        pytest.param("foo", '"foo"', id="string"),
        pytest.param(1, "1", id="int"),
        pytest.param(None, "None", id="none"),
        pytest.param(True, "True", id="bool"),
        pytest.param("It's mine", '"It\\\'s mine"', id="single-quote"),
        pytest.param('It is "mine"', '"It is \\\"mine\\\""', id="double-quote"),
    ]
)
def test_maybe_quoted(item, expected):
    assert expected == maybe_quoted(item)


@pytest.mark.parametrize(
    ["obj", "name", "value", "expected"],
    [
        pytest.param({"a": "b"}, "c", "d", {"a": "b", "c": ["d"]}, id="added"),
        pytest.param({"a": "b", "c": ["d"]}, "c", "e", {"a": "b", "c": ["e", "d"]}, id="inserted"),
        pytest.param({"a": "b", "c": None}, "c", "e", {"a": "b", "c": ["e"]}, id="none"),
    ]
)
def test_prepend(obj, name, value, expected):
    prepend(obj, name, value)
    assert expected == obj


@pytest.mark.parametrize(
    ["orig", "replacement", "expected"],
    [
        pytest.param("", "_", "", id="empty"),
        pytest.param("a+b", "_", "a_b", id="underscore"),
        pytest.param("a+b", "*", "a*b", id="star"),
        pytest.param("a*b", None, "ab", id="none"),
    ]
)
def test_replace_special(orig, replacement, expected):
    actual = replace_special(orig, replacement)
    assert expected == actual


@pytest.mark.parametrize(
    ["obj", "name", "value", "expected"],
    [
        pytest.param({"a": "b"}, "c", True, {"a": "b", "c": True}, id="missing"),
        pytest.param({"a": "b"}, "a", 1, {"a": "b"}, id="exists"),
    ],
)
def test_set_missing(obj, name, value, expected):
    set_missing(obj, name, value)
    assert expected == obj


@pytest.mark.parametrize(
    ["obj", "expected"],
    [
        pytest.param({}, "{}", id="empty"),
        pytest.param({"single": "value"}, "{single: value}", id="single"),
        pytest.param({"a": 1, "B": True, "c": "foo"}, "{a: 1, B: True, c: foo}", id="simple"),
        pytest.param({"a": ["a", "b"], "z": {"a": 1, "b": 2}}, "{a: [...], z: {...}}", id="collections"),
        pytest.param(
            {"a": "this is a long text value that goes more than the specified"},
            "{a: this is a long text value that goes more than t...}",
            id="long",
        ),
    ]
)
def test_shallow(obj, expected):
    assert expected == shallow(obj)


@pytest.mark.parametrize(
    ["items", "expected"],
    [
        pytest.param([], False, id="empty"),
        pytest.param(["a", "B", 1, False], False, id="simple"),
        pytest.param(["a", "B", "A"], True, id="overlap"),
        pytest.param(["a", "a"], False, id="duplicate"),
    ]
)
def test_is_case_sensitive(items, expected):
    assert expected == is_case_sensitive(items)
