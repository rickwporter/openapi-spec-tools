import pytest

from openapi_spec_tools.cli_gen.utils import maybe_quoted
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
    ]
)
def test_maybe_quoted(item, expected):
    assert expected == maybe_quoted(item)

