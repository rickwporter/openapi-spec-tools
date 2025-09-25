import pytest

from openapi_spec_tools.api_gen.property_generator import PropertyApiGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.api_gen.constants import *  # noqa: F403
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["reference", "prop_names"],
    [
        pytest.param(
            "/components/schemas/PetExt",
            {
                'anotherValue',
                'name',
                'tag',
                'bogus',
                'flavor',
                'binString',
                'optionalList',
                'firstChoice',
                'listVarious',
                'format',
                'gone',
                'bestDay',
                'owner',
                'inconsistent',
                'nonListDef',
            },
            id="all-of",
        ),
        pytest.param(
            "/components/schemas/MultipleAnyOf",
            {'anotherValue', 'name', 'tag'},
            id="any-of",
        ),
        pytest.param(
            "/components/schemas/ShapeShifter",
            {'species'},
            id="one-of",
        ),
        pytest.param(
            "#/components/schemas/EnumListProperty",
            {'rainbow'},
            id="list",
        ),
        pytest.param(
            "#/components/schemas/MissingItemsModel",
            {'foo', 'bar'},
            id="missing-submodel"
        )
    ]
)
def test_model_properties(reference, prop_names):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = PropertyApiGenerator("api_package", oas)
    model = uut.get_model(reference)
    body_params = uut.model_properties("foo", model)

    assert prop_names == set(body_params.keys())


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = PropertyApiGenerator("api_package", oas)
    body_params = uut.op_body_top_properties(op)

    args = uut.op_body_arguments(body_params)
    text = "\n".join(args)

    assert 'name: str = None,  # Pet name' in text
    assert 'tag: Optional[str] = None,  # Pet classification' in text
    assert 'another_value: Optional[str] = "Anything goes",  # A string with a default' in text
    assert 'flavor: Any = None,  # see Species for info' in text
    assert 'bin_string: Optional[str] = "4",  # choices: 1, 2, 4, 8' in text
    assert 'optional_list: Any = None,' in text
    assert 'first_choice: Any = None,' in text
    assert 'list_various: Any = None,' in text
    assert 'format_: Optional[str] = "text",' in text
    assert 'gone: Optional[str] = None,  # To be removed' in text
    assert 'best_day: Any = None,  # enum buried in all-of' in text
    assert 'inconsistent: Optional[int] = 2,  # choices: 1, 2, infinity-and-beyond' in text
    assert 'non_list_def: Any = 1.1,' in text

    # this is filtered out bu the op_body_settable_properties
    assert 'bogus: Annotated' not in text

    # make sure read-only not included
    assert 'id: Annotated' not in text


def test_function_definition():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snaFooCreate')
    uut = PropertyApiGenerator("api_package", oas)
    text = uut.function_definition(item)
    assert 'def sna_foo_create(' in text
    assert 'attachments: Optional[list[dict[str, Any]]] = None,  # see Attachment for info' in text
    assert '# handler for snaFooCreate: POST /sna/foo' in text

    # check infra arguments
    assert '_api_host: Optional[str] = None,' in text
    assert '_api_key: Optional[str] = None,' in text
    assert '_api_timeout: Optional[int] = None,' in text
    assert '_log_level: Optional[str] = None,' in text

    # check infra initialization/defaults
    assert '_api_host = _api_host or _e.env_string("API_HOST"' in text
    assert '_api_key = _api_key or _e.env_string("API_KEY"' in text
    assert '_api_timeout = _api_timeout or _e.env_int("API_TIMEOUT"' in text
    assert '_log_level = _log_level or _e.env_string("API_LOG_LEVEL"' in text

    # check the body of the function
    assert "_l.init_logging(_log_level)" in text
    assert 'headers = _r.request_headers(_api_key, content_type="application/json")' in text
    assert 'url = _r.create_url(_api_host, "sna/foo")' in text

    assert 'params = {}' in text
    assert 'body = {}' in text
    assert 'if attachments is not None:' in text
    assert 'body["attachments"] = attachments' in text
    assert 'data = _r.request("POST", url, headers=headers, params=params, body=body, timeout=_api_timeout)' in text


def test_function_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooCheck')
    uut = PropertyApiGenerator("api_package", oas)
    text = uut.function_definition(item)

    assert 'def snafoo_check(' in text

    # check infra arguments
    assert '_api_host: Optional[str] = None,' in text
    assert '_api_key: Optional[str] = None,' in text
    assert '_api_timeout: Optional[int] = None,' in text
    assert '_log_level: Optional[str] = None,' in text

    # check the warning log
    assert '_l.logger().warning("snafooCheck is deprecated and should not be used.")' in text


def test_function_x_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooDelete')
    uut = PropertyApiGenerator("api_package", oas)
    text = uut.function_definition(item)

    assert 'def snafoo_delete(' in text

    # check infra arguments
    assert '_api_host: Optional[str] = None,' in text
    assert '_api_key: Optional[str] = None,' in text
    assert '_api_timeout: Optional[int] = None,' in text
    assert '_log_level: Optional[str] = None,' in text

    # check the warning log
    assert '_l.logger().warning("snafooDelete was deprecated in 3.2.1, and should not be used.")' in text


def test_function_header_params():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='testPathParams')
    uut = PropertyApiGenerator("api_package", oas)
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
