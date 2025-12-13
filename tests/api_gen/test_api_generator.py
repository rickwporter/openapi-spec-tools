import pytest

from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.api_gen.constants import DESC
from tests.api_gen.constants import ENUM
from tests.api_gen.constants import REQUIRED
from tests.api_gen.constants import SUM
from tests.api_gen.constants import X_REF
from tests.api_gen.helpers import TestApiGenerator
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["prop", "max_len", "expected"],
    [
        pytest.param({}, 10, "", id="empty"),
        pytest.param({SUM: "Short summary. With sentence."}, 50, "  # Short summary. With sentence.", id="sum-sent"),
        pytest.param({DESC: "Short desc. With sentence."}, 50, "  # Short desc. With sentence.", id="desc-sent"),
        pytest.param({DESC: "Description", SUM: "Summary"}, 50, "  # Summary", id="both"),
        pytest.param({SUM: "Short summary. With sentence."}, 25, "  # Short summary...", id="sentence"),
        pytest.param({SUM: "Short summary. With sentence."}, 10, "  # Short summ...", id="truncated"),
        pytest.param({REQUIRED: True, SUM: "some help"}, 100, "  # some help [required]", id="required"),
        pytest.param({REQUIRED: True, SUM: "Requires some help"}, 100, "  # Requires some help", id="req-desc"),
        pytest.param({REQUIRED: True}, 100, "  # [required]", id="req-only"),
        pytest.param({REQUIRED: True, X_REF: "RefName"}, 100, "  # see RefName for info [required]", id="req-ref"),
        pytest.param({ENUM: ["a", "t", 0]}, 100, "  # choices: a, t, 0", id="enum"),
        pytest.param({X_REF: "ShortReferenceName"}, 100, "  # see ShortReferenceName for info", id="ref")
    ]
)
def test_property_help(prop, max_len, expected):
    uut = TestApiGenerator("", {}, max_help_length=max_len)
    assert expected == uut.property_help(prop)


def test_standard_imports():
    uut = TestApiGenerator("api_package", {})
    text = uut.standard_imports()
    assert 'from typing import Any' in text
    assert 'from datetime import datetime' in text
    assert 'from api_package import _environment as _e' in text

@pytest.mark.parametrize(
    ["args", "default_host", "expected"],
    [
        pytest.param(
            {},
            None,
            """\
_api_host: Optional[str] = None,  # API host, read from API_HOST if not provided
_api_key: Optional[str] = None,  # API key for bearer auth, read from API_KEY if not provided
_api_timeout: Optional[int] = None,  # timeout for operation, read from API_TIMEOUT if not provided, defaults to 5
_log_level: Optional[str] = None,  # log level, read from API_LOG_LEVEL if not provided, defaults to info\
""",
            id="defaults",
        ),
        pytest.param(
            {
                "env_host": "MY_HOST",
                "env_key": "YOUR_KEY",
                "env_timeout": "THEIR_TIME",
                "default_timeout": 30,
                "env_log_level": "SOME_LOG_LEVEL",
                "default_log_level": "blah",
            },
            "localhost",
            """\
_api_host: Optional[str] = None,  # API host, read from MY_HOST if not provided, defaults to localhost
_api_key: Optional[str] = None,  # API key for bearer auth, read from YOUR_KEY if not provided
_api_timeout: Optional[int] = None,  # timeout for operation, read from THEIR_TIME if not provided, defaults to 30
_log_level: Optional[str] = None,  # log level, read from SOME_LOG_LEVEL if not provided, defaults to blah\
""",
            id="updates",
        )
    ]
)
def test_command_infra_arguments(
    args, default_host,
    expected,
):
    uut = TestApiGenerator("api_package", {}, **args)
    uut.default_host = default_host
    node = LayoutNode(command="foo", identifier="bar")
    args = uut.command_infra_arguments(node)
    text = "\n".join(args)
    assert expected == text


def test_op_path_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = TestApiGenerator("api_package", oas)
    path_params = uut.op_params(op, "path")

    args = uut.op_path_arguments(path_params)
    text = "\n".join(args)

    assert 'num_feet: Optional[int] = None,  # Number of feet' in text
    assert 'species: Optional[str] = "monkey",  # Species name in Latin without spaces' in text
    assert 'neutered: Optional[bool] = True,  # Ouch' in text
    assert 'birthday: Optional[datetime] = None,  # When is the party?' in text
    assert 'must_have: str,' in text
    assert 'your_boat: float = 3.14159,  # Pi is always good' in text
    assert 'foobar: Optional[Any] = None,' in text

    # make sure we ignore the query params
    assert 'situation: ' not in text
    assert 'more: ' not in text


def test_op_query_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = TestApiGenerator("api_package", oas)
    query_params = uut.op_params(op, "query")
    properties = uut.params_to_settable_properties(query_params)

    args = uut.op_query_arguments(properties)
    text = "\n".join(args)

    assert 'situation: str = "anything goes",  # Query param at path level, likely unused' in text
    assert 'limit: Optional[int] = None,  # How many items to return at one time (max 100)' in text
    assert 'another_qparam: str = None,  # Query parameter' in text
    assert 'more: Optional[bool] = False,' in text
    assert 'day_value: Optional[DayValue] = None,' in text
    assert 'page_size: Optional[int] = 100,  # Maximum items per page' in text
    assert 'str_list_prop: Optional[list[str]] = None,' in text
    assert 'enum_with_default: Optional[EnumWithDefault] = "TheOtherThing",' in text
    assert 'str_enum_with_int_values: Optional[StrEnumWithIntValues] = "1",' in text
    assert 'type_: Optional[int] = None,' in text
    assert 'param_with_enum_ref: Optional[ParamWithEnumRef] = "frog",  # Species type' in text
    assert 'addr_street: Optional[str] = None,  # Street address (e.g. 123 Main Street, POBox 507)' in text
    assert 'addr_city: Optional[str] = None,' in text
    assert 'addr_state: Optional[str] = None,' in text
    assert 'addr_zip_code: str = None,' in text
    assert 'favorite_day: Optional[FavoriteDay] = None,' in text
    assert 'crazy_enum: Optional[CrazyEnum] = "1.0",' in text
    assert 'list_enum_def_list: Optional[list[ListEnumDefList]] = [\'1\', \'8\'],' in text
    assert 'list_int_enum: Optional[list[ListIntEnum]] = [7],' in text

    # make sure path params not included
    assert 'num_feet: Annotated' not in text
    assert 'must_have: Annotated' not in text
