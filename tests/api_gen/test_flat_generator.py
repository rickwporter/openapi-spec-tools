from openapi_spec_tools.api_gen.flat_generator import FlatApiGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.api_gen.constants import *  # noqa: F403
from tests.helpers import asset_filename


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = FlatApiGenerator("api_package", oas)
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


def test_function_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = FlatApiGenerator("api_package", oas)
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
    uut = FlatApiGenerator("api_package", oas)
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
    uut = FlatApiGenerator("api_package", oas)
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
    uut = FlatApiGenerator("api_package", oas)
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
