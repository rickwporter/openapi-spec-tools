import pytest

from openapi_spec_tools.api_gen.opaque_generator import OpaqueApiGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.utils import open_oas
from tests.api_gen.constants import DESC
from tests.api_gen.constants import REQUIRED
from tests.api_gen.constants import TYPE
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["params", "expected"],
    [
        pytest.param({}, [], id="empty"),
        pytest.param({DESC: "my party"}, ["body: Any = None,  # my party"], id="desc"),
        pytest.param({"x-reference": "SomeBodyType"}, ["body: Any = None,  # see SomeBodyType for info"], id="ref"),
        pytest.param({REQUIRED: ["a", "b", "z"]}, ["body: Any = None,  # required fields: a, b, z"], id="req"),
        pytest.param({TYPE: "object"}, ["body: Any = None,  # no info available"], id="none")
    ]
)
def test_op_body_arguments(params, expected):
    uut = OpaqueApiGenerator("api_package", {})
    args = uut.op_body_arguments(params)
    assert expected == args


def test_function_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = OpaqueApiGenerator("api_package", oas)
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
    uut = OpaqueApiGenerator("api_package", oas)
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
    uut = OpaqueApiGenerator("api_package", oas)
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
    uut = OpaqueApiGenerator("api_package", oas)
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
