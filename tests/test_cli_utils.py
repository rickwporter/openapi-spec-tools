import pytest

from oas_tools.cli_gen.utils import to_camel_case
from oas_tools.cli_gen.utils import to_snake_case


@pytest.mark.parametrize(
    ["text", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("foobar", "foobar", id="lowercase"),
        pytest.param("foo_bar", "foo_bar", id="unchanged"),
        pytest.param("FooBar", "foo_bar", id="simple"),
        pytest.param("FOOBar", "foo_bar", id="multi-caps"),
        pytest.param("SnaFooBar123_MORE", "sna_foo_bar123_more", id="numbers"),
    ]
)
def test_snake_case(text, expected) -> None:
    assert expected == to_snake_case(text)


@pytest.mark.parametrize(
    ["text", "expected"],
    [
        pytest.param("", "", id="empty"),
        pytest.param("foobar", "foobar", id="lowercase"),
        pytest.param("FooBar", "FooBar", id="unchanged"),
        pytest.param("foo_bar", "fooBar", id="simple"),
        pytest.param("sna_foo_bar123_more", "snaFooBar123More", id="numbers"),
    ]
)
def test_camel_case(text, expected) -> None:
    assert expected == to_camel_case(text)
