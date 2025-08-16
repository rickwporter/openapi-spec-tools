import pytest

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.helpers import asset_filename

SUM = "summary"
DESC = "description"
TYPE = "type"
FORMAT = "format"
REQUIRED = "required"
COLLECT = "x-collection"
ENUM = "enum"
SCHEMA = "schema"
ANY_OF = "anyOf"
ONE_OF = "oneOf"
ITEMS = "items"
DEF = "default"

S1 = '\n    '
S2 = f"{S1}    "


@pytest.mark.parametrize(
    ["prop", "max_len", "expected"],
    [
        pytest.param({}, 10, "", id="empty"),
        pytest.param({SUM: "Short summary. With sentence."}, 50, "  # Short summary. With sentence.", id="sum-sent"),
        pytest.param({DESC: "Short desc. With sentence."}, 50, "  # Short desc. With sentence.", id="desc-sent"),
        pytest.param({DESC: "Description", SUM: "Summary"}, 50, "  # Summary", id="both"),
        pytest.param({SUM: "Short summary. With sentence."}, 25, "  # Short summary", id="sentence"),
        pytest.param({SUM: "Short summary. With sentence."}, 10, "  # Short summ", id="truncated"),
    ]
)
def test_property_help(prop, max_len, expected):
    uut = ApiGenerator("", {})
    uut.max_help_length = max_len
    assert expected == uut.property_help(prop)


def test_standard_imports():
    uut = ApiGenerator("api_package", {})
    text = uut.standard_imports()
    assert 'from typing import Any' in text
    assert 'from datetime import datetime' in text
    assert 'from api_package import _environment as _e' in text


def test_op_path_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = ApiGenerator("api_package", oas)
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
    uut = ApiGenerator("api_package", oas)
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


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = ApiGenerator("api_package", oas)
    body_params = uut.op_body_settable_properties(op)

    args = uut.op_body_arguments(body_params)
    text = "\n".join(args)

    assert 'name: str = None,  # Pet name' in text
    assert 'tag: Optional[str] = None,  # Pet classification' in text
    assert 'another_value: Optional[str] = "Anything goes",  # A string with a default' in text
    assert 'flavor: Optional[Flavor] = None,  # Species type' in text
    assert 'bin_string: Optional[BinString] = "4",' in text
    assert 'optional_list: Optional[list[str]] = None,' in text
    assert 'first_choice: Optional[int] = None,' in text
    assert 'list_various: Optional[list[bool]] = None,' in text
    assert 'format_: Optional[str] = "text",' in text
    assert 'gone: Optional[str] = None,  # To be removed' in text
    assert 'best_day: Optional[BestDay] = None,  # enum buried in all-of' in text
    assert 'inconsistent: Optional[Inconsistent] = "2",' in text
    assert 'non_list_def: Optional[list[NonListDef]] = ["1.1"],' in text

    # this is filtered out bu the op_body_settable_properties
    assert 'bogus: Annodated' not in text

    # make sure read-only not included
    assert 'id: Annotated' not in text


def test_op_infra_arguments():
    command = LayoutNode("foo", "foo")
    oas = open_oas(asset_filename("misc.yaml"))
    uut = ApiGenerator("api_package", oas)

    args = uut.command_infra_arguments(command)
    text = "\n".join(args)

    # check standard arguments
    assert '_api_host: str = _e.env_str("API_HOST", "http://petstore.swagger.io/v1"),  # host URL' in text
    assert '_api_key: str = _e.env_str("API_KEY"),  # API key for bearer authentication' in text
    assert '_api_timeout: int = _e.env("API_TIMEOUT", 5),  # timeout for operation' in text
    assert '_log_level: str = _e.env("API_LOG_LEVEL", "info"),  # log level' in text


def test_function_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = ApiGenerator("api_package", oas)
    text = uut.function_definition(item)
    assert 'def create_pets(' in text
    assert '# handler for createPets: POST /pets' in text

    # check standard arguments
    assert '_api_host: str = _e.env_str("API_HOST", "http://petstore.swagger.io/v1"),  # host URL' in text
    assert '_api_key: str = _e.env_str("API_KEY"),  # API key for bearer authentication' in text
    assert '_api_timeout: int = _e.env("API_TIMEOUT", 5),  # timeout for operation' in text
    assert '_log_level: str = _e.env("API_LOG_LEVEL", "info"),  # log level' in text

    # check the body of the function
    assert "_l.init_logging(_log_level)" in text
    assert 'headers = _r.request_headers(_api_key, content_type="application/json")' in text
    assert 'url = _r.create_url(_api_host, "pets")' in text
    assert 'params = {}' in text


def test_function_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooCheck')
    uut = ApiGenerator("api_package", oas)
    text = uut.function_definition(item)

    assert 'def snafoo_check(' in text

    # check a couple arguments
    assert '_api_host: str = _e.env_str("API_HOST", "http://petstore.swagger.io/v1"),  # host URL' in text
    assert '_api_key: str = _e.env_str("API_KEY"),  # API key for bearer authentication' in text
    assert '_api_timeout: int = _e.env("API_TIMEOUT", 5),  # timeout for operation' in text
    assert '_log_level: str = _e.env("API_LOG_LEVEL", "info"),  # log level' in text

    # check the warning log
    assert '_l.logger().warning("snafooCheck is deprecated and should not be used.")' in text


def test_function_x_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooDelete')
    uut = ApiGenerator("api_package", oas)
    text = uut.function_definition(item)

    assert 'def snafoo_delete(' in text

    # check a couple arguments
    assert '_api_host: str = _e.env_str("API_HOST", "http://petstore.swagger.io/v1"),  # host URL' in text
    assert '_api_key: str = _e.env_str("API_KEY"),  # API key for bearer authentication' in text
    assert '_api_timeout: int = _e.env("API_TIMEOUT", 5),  # timeout for operation' in text
    assert '_log_level: str = _e.env("API_LOG_LEVEL", "info"),  # log level' in text

    # check the warning log
    assert '_l.logger().warning("snafooDelete was deprecated in 3.2.1, and should not be used.")' in text


def test_function_header_params():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='testPathParams')
    uut = ApiGenerator("api_package", oas)
    text = uut.function_definition(item)

    # check that the header enums are defined -- no need to check all the fields of each enum
    assert 'class Color(str, Enum):' in text

    # check function argument (aka CLI option)
    assert 'has_param: int = None,  # Parameter in header' in text
    assert 'color: Optional[Color] = None,' in text

    # make sure we add to headers
    assert 'user_headers = {}' in text
    assert 'if has_param is not None:' in text
    assert 'user_headers["hasParam"] = has_param' in text
    assert (
        'headers = _r.request_headers(_api_key, content_type="application/json", **user_headers)'
        in text
    )
