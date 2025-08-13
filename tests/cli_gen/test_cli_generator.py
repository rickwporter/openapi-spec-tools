from pathlib import Path

import pytest

from openapi_spec_tools.cli_gen.cli_generator import CliGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
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

def test_standard_imports():
    uut = CliGenerator("cli_package", {})
    text = uut.standard_imports()
    assert "import typer" in text
    assert "from typing import Annotated" in text


def test_subcommand_imports():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = CliGenerator("cli_package", oas)
    text = uut.subcommand_imports(tree.subcommands())
    for name in ["pets", "owners", "veterinarians"]:
        line = f"from cli_package.{name} import app as {name}"
        assert line in text


def test_app_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = CliGenerator("cli_package", oas)
    text = uut.app_definition(tree)
    assert 'app = typer.Typer(no_args_is_help=True, help="Pet management application")' in text
    for name, command in {
        "pets": "pet",
        "owners": "owners",
        "veterinarians": "vets",
    }.items():
        # NOTE: this is not universal, but works here
        line = f'app.add_typer({name}, name="{command}")'
        assert line in text


def test_op_path_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = CliGenerator("cli_package", oas)
    path_params = uut.op_params(op, "path")

    lines = uut.op_path_arguments(path_params)
    text = "\n".join(lines)

    assert 'num_feet: Annotated[Optional[int], typer.Option(show_default=False, help="Number of feet")] = None' in text
    assert (
        'species: Annotated[Optional[str], typer.Option(help="Species name in Latin without spaces")] = "monkey"'
        in text
    )
    assert 'neutered: Annotated[Optional[bool], typer.Option(hidden=True, help="Ouch")] = True' in text
    assert (
        'birthday: Annotated[Optional[datetime], typer.Option(show_default=False, help="When is the party?")] = None'
        in text
    )
    assert 'must_have: Annotated[str, typer.Argument(show_default=False)]' in text
    assert 'your_boat: Annotated[float, typer.Option(help="Pi is always good")] = 3.14159' in text
    assert 'foobar: Annotated[Optional[Any], typer.Option(show_default=False, hidden=True)] = None' in text

    # make sure we ignore the query params
    assert 'situation: Annotated' not in text
    assert 'more: Annotated' not in text


def test_op_query_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = CliGenerator("cli_package", oas)
    query_params = uut.op_params(op, "query")
    properties = uut.params_to_settable_properties(query_params)

    lines = uut.op_query_arguments(properties)
    text = "\n".join(lines)

    assert (
        'situation: Annotated[str, typer.Option(help="Query param at path level, likely unused")] = "anything goes"'
        in text
    )
    assert (
        'limit: Annotated[Optional[int], typer.Option(min=1, max=100, '
        'show_default=False, help="How many items to return at one time (max 100)")] = None'
        in text
    )
    assert (
        'another_qparam: Annotated[str, typer.Option(show_default=False, help="Query parameter")] = None'
        in text
    )
    assert 'more: Annotated[Optional[bool], typer.Option(hidden=True)] = False' in text
    assert (
        'day_value: Annotated[Optional[DayValue], '
        'typer.Option(show_default=False, case_sensitive=False, hidden=True)] = None'
        in text
    )
    assert (
        'page_size: Annotated[Optional[int], typer.Option(help="Maximum items per page")] = 100'
        in text
    )
    assert (
        'str_list_prop: Annotated[Optional[list[str]], typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'enum_with_default: Annotated[Optional[EnumWithDefault], typer.Option(case_sensitive=False)] = "TheOtherThing"'
        in text
    )
    assert (
        'str_enum_with_int_values: Annotated[Optional[StrEnumWithIntValues], typer.Option(case_sensitive=False)] = "1"'
        in text
    )
    assert (
        'type_: Annotated[Optional[int], typer.Option("--type", show_default=False)] = None'
        in text
    )
    assert (
        'param_with_enum_ref: Annotated[Optional[ParamWithEnumRef], typer.Option(case_sensitive=False, '
        'help="Species type")] = "frog"'
        in text
    )
    assert (
        'addr_street: Annotated[Optional[str], typer.Option(show_default=False, '
        'help="Street address (e.g. 123 Main Street, POBox 507)")] = None'
        in text
    )
    assert (
        'addr_city: Annotated[Optional[str], typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'addr_state: Annotated[Optional[str], typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'addr_zip_code: Annotated[str, typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'favorite_day: Annotated[Optional[FavoriteDay], typer.Option(show_default=False, '
        'case_sensitive=True)] = None'
        in text
    )
    assert (
        'crazy_enum: Annotated[Optional[CrazyEnum], typer.Option(case_sensitive=False)] = "1.0"'
        in text
    )
    assert (
        'list_enum_def_list: Annotated[Optional[list[ListEnumDefList]], typer.Option(case_sensitive=False)] '
        "= ['1', '8']"
        in text
    )
    assert (
        'list_int_enum: Annotated[Optional[list[ListIntEnum]], typer.Option(case_sensitive=False)] = [7]'
        in text
    )

    # make sure path params not included
    assert 'num_feet: Annotated' not in text
    assert 'must_have: Annotated' not in text


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = CliGenerator("cli_package", oas)
    body_params = uut.op_body_settable_properties(op)

    lines = uut.op_body_arguments(body_params)
    text = "\n".join(lines)
    assert 'name: Annotated[str, typer.Option(show_default=False, help="Pet name")] = None' in text
    assert 'tag: Annotated[Optional[str], typer.Option(show_default=False, help="Pet classification")] = None' in text
    assert (
        'another_value: Annotated[Optional[str], typer.Option(hidden=True, '
        'help="A string with a default")] = "Anything goes"'
        in text
    )
    assert (
        'flavor: Annotated[Optional[Flavor], '
        'typer.Option(show_default=False, case_sensitive=False, help="Species type")] = None'
        in text
    )
    assert (
        'bin_string: Annotated[Optional[BinString], typer.Option(case_sensitive=False)] = "4"'
        in text
    )
    assert(
        'optional_list: Annotated[Optional[list[str]], typer.Option(show_default=False)] = None'
        in text
    )
    assert(
        'first_choice: Annotated[Optional[int], typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'list_various: Annotated[Optional[list[bool]], typer.Option(show_default=False)] = None'
        in text
    )
    assert (
        'format_: Annotated[Optional[str], typer.Option("--format")] = "text"'
        in text
    )
    assert (
        'gone: Annotated[Optional[str], typer.Option(show_default=False, hidden=True, '
        'help="To be removed")] = None'
        in text
    )
    assert (
        'best_day: Annotated[Optional[BestDay], typer.Option(show_default=False, '
        'case_sensitive=True, help="enum buried in all-of")] = None'
        in text
    )
    assert (
        'inconsistent: Annotated[Optional[Inconsistent], typer.Option(case_sensitive=False)] = "2"'
        in text
    )
    assert (
        'non_list_def: Annotated[Optional[list[NonListDef]], typer.Option(case_sensitive=False)] = ["1.1"]'
        in text
    )

    # this is filtered out bu the op_body_settable_properties
    assert 'bogus: Annodated' not in text

    # make sure read-only not included
    assert 'id: Annotated' not in text


@pytest.mark.parametrize(
    ["names", "expected"],
    [
        pytest.param(None, "", id="None"),
        pytest.param(PaginationNames(), f"page_info = _r.PageParams({S2}max_count=_max_count,{S1})", id="empty"),
        pytest.param(
            PaginationNames(page_size="fooBar"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}page_size_name="fooBar",'
            f'{S2}page_size_value=foo_bar,{S1})',
            id="page_size",
        ),
        pytest.param(
            PaginationNames(page_start="snaFoo"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}page_start_name="snaFoo",'
            f'{S2}page_start_value=sna_foo,{S1})',
            id="page_start",
        ),
        pytest.param(
            PaginationNames(item_start="eastWest"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}item_start_name="eastWest",'
            f'{S2}item_start_value=east_west,{S1})',
            id="item_start",
        ),
        pytest.param(
            PaginationNames(items_property="northSouth"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}items_property_name="northSouth",{S1})',
            id="items_property",
        ),
        pytest.param(
            PaginationNames(next_header="upDown"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}next_header_name="upDown",{S1})',
            id="next_header",
        ),
        pytest.param(
            PaginationNames(next_property="leftRight"),
            f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}next_property_name="leftRight",{S1})',
            id="next_property",
        ),
    ]
)
def test_pagination_creation(names, expected) -> None:
    node = LayoutNode(command="foo", identifier="bar", pagination=names)
    uut = CliGenerator("foo", {})
    result = uut.pagination_creation(node)
    assert expected == result.strip()

@pytest.mark.parametrize(
    ["command", "has_details"],
    [
        pytest.param(LayoutNode("foo", "foo"), False, id="no-summary"),
        pytest.param(LayoutNode("foo", "foo", summary_fields=["abc"]), True, id="summary"),
    ],
)
def test_op_infra_arguments(command, has_details):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = CliGenerator("cli_package", oas)

    lines = uut.command_infra_arguments(command)
    text = "\n".join(lines)

    # check standard arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text
    assert "_api_timeout: _a.ApiTimeoutOption" in text
    assert "_log_level: _a.LogLevelOption" in text
    assert "_out_fmt: _a.OutputFormatOption" in text
    assert "_out_style: _a.OutputStyleOption" in text
    details_option = '_details: _a.DetailsOption'
    if has_details:
        assert details_option in text
    else:
        assert details_option not in text

    # check that we got the correct default server
    assert '= "http://petstore.swagger.io/v1"' in text


def test_op_check_missing():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = CliGenerator("cli_package", oas)
    query_params = uut.op_params(op, "query")
    body_params = uut.op_body_settable_properties(op)

    text = uut.op_check_missing(query_params, body_params)

    # infra
    assert 'if _api_key is None:' in text
    assert 'missing.append("--api-key")' in text

    # query parameters
    assert 'if another_qparam is None:' in text
    assert 'missing.append("--another-qparam")' in text
    assert 'if more is None' not in text  # only required

    # body params
    assert 'missing.append("--name")' in text
    assert 'missing.append("--id")' not in text  # not read-only
    assert 'missing.append("--tag")' not in text  # only required


def test_summary_display():
    uut = CliGenerator("foo", {})

    command = LayoutNode("foo", "foo", summary_fields=["abc", "defGhi"])
    text = uut.summary_display(command)
    assert 'if not _details:' in text
    assert 'data = _d.summary(data, ["abc", "defGhi"])' in text

    command = LayoutNode("foo", "foo")
    text = uut.summary_display(command)
    assert '' == text


def test_function_definition_item():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)
    assert '@app.command("create", short_help="Create a pet")' in text
    assert 'def create_pets(' in text
    assert '# handler for createPets: POST /pets' in text

    # check standard arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text
    assert "_api_timeout: _a.ApiTimeoutOption" in text
    assert "_log_level: _a.LogLevelOption" in text
    assert "_out_fmt: _a.OutputFormatOption" in text
    assert "_out_style: _a.OutputStyleOption" in text
    assert "_details: _a.DetailsOption" in text

    # check the body of the function
    assert "_l.init_logging(_log_level)" in text
    assert 'headers = _r.request_headers(_api_key, content_type="application/json")' in text
    assert 'url = _r.create_url(_api_host, "pets")' in text
    assert 'params = {}' in text
    assert 'data = _r.request("POST", url, headers=headers, params=params, body=body, timeout=_api_timeout)' in text
    assert '_d.display(data, _out_fmt, _out_style)' in text
    assert '_e.handle_exceptions(ex)' in text
    assert 'data = _d.summary(data, ["name"])' in text

    # make sure the missing parameter checks are present
    assert 'missing.append("--api-key")' in text
    assert 'missing.append("--name")' in text
    assert ' _e.handle_exceptions(_e.MissingRequiredError(missing))' in text


def test_function_definition_bad_body():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command="create", identifier="snaFooCreate")
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)
    assert '@app.command("create", short_help="Create a normally messed up situation")' in text
    assert 'def sna_foo_create(' in text
    assert '# handler for snaFooCreate: POST /sna/foo' in text

    # check standard arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text
    assert "_api_timeout: _a.ApiTimeoutOption" in text
    assert "_log_level: _a.LogLevelOption" in text
    assert "_out_fmt: _a.OutputFormatOption" in text
    assert "_out_style: _a.OutputStyleOption" in text

    # no summary field, so no details flag
    assert "_details: _a.DetailsOption" not in text

    # body is just a complex list, so not added
    assert "body = " not in text

    # check the body of the function
    assert "_l.init_logging(_log_level)" in text
    assert 'headers = _r.request_headers(_api_key, content_type="application/json")' in text
    assert 'url = _r.create_url(_api_host, "sna/foo")' in text
    assert 'params = {}' in text
    assert 'data = _r.request("POST", url, headers=headers, params=params, timeout=_api_timeout)' in text
    assert '_d.display(data, _out_fmt, _out_style)' in text
    assert '_e.handle_exceptions(ex)' in text

    # make sure the missing parameter checks are present
    assert 'missing.append("--api-key")' in text
    assert ' _e.handle_exceptions(_e.MissingRequiredError(missing))' in text


def test_function_definition_paged():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets.yaml"))
    item = tree.find("list")
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)

    assert '@app.command("list", short_help="List all pets")' in text
    assert 'def list_pets(' in text

    # check arguments
    assert (
        'limit: Annotated[Optional[int], typer.Option(max=100, show_default=False, '
        'help="How many items to return at one time (max 100)")]'
        in text
    )
    assert '_api_host: _a.ApiHostOption' in text
    assert '_log_level: _a.LogLevelOption' in text
    assert '_max_count: _a.MaxCountOption' in text

    # double check a few important body differences
    assert (
        f'page_info = _r.PageParams({S2}max_count=_max_count,{S2}page_size_name="limit",{S2}page_size_value=limit,{S1})'
        in text
    )
    assert 'data = _r.depaginate(page_info, url, headers=headers, params=params, timeout=_api_timeout)' in text


def test_function_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooCheck')
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)

    assert '@app.command("sna", hidden=True, short_help="Check on how messed up things are")' in text
    assert 'def snafoo_check(' in text

    # check a couple arguments
    assert '_api_host: _a.ApiHostOption' in text
    assert '_log_level: _a.LogLevelOption' in text

    # check the warning log
    assert '_l.logger().warning("snafooCheck is deprecated and should not be used.")' in text


def test_function_x_deprecated():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='snafooDelete')
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)

    assert '@app.command("sna", hidden=True, short_help="Straighten things out")' in text
    assert 'def snafoo_delete(' in text

    # check a couple arguments
    assert '_api_host: _a.ApiHostOption' in text
    assert '_log_level: _a.LogLevelOption' in text

    # check the warning log
    assert '_l.logger().warning("snafooDelete was deprecated in 3.2.1, and should not be used.")' in text


def test_function_header_params():
    oas = open_oas(asset_filename("misc.yaml"))
    item = LayoutNode(command='sna', identifier='testPathParams')
    uut = CliGenerator("cli_package", oas)
    text = uut.function_definition(item)

    # check that the header enums are defined -- no need to check all the fields of each enum
    assert 'class Color(str, Enum):' in text

    # check function argument (aka CLI option)
    assert (
        'has_param: Annotated[int, typer.Option(show_default=False, help="Parameter in header")] = None'
        in text
    )
    assert (
        'color: Annotated[Optional[Color], typer.Option(show_default=False, case_sensitive=False)] = None'
        in text
    )

    # make sure we add to headers
    assert 'user_headers = {}' in text
    assert 'if has_param is None:' in text
    assert 'user_headers["hasParam"] = has_param' in text
    assert (
        'headers = _r.request_headers(_api_key, content_type="application/json", **user_headers)'
        in text
    )

    # make sure the missing parameter checks are present
    assert 'if has_param is None:' in text
    assert 'missing.append("--has-param")' in text
    assert ' _e.handle_exceptions(_e.MissingRequiredError(missing))' in text


def test_main():
    uut = CliGenerator("cli_package", {})
    text = uut.main()
    assert 'if __name__ == "__main__":' in text
    assert "app()" in text


@pytest.mark.parametrize(
    ["oas_filename", "layout_filename", "expected"],
    [
        pytest.param(
            "pet2.yaml",
            "layout_pets.yaml",
            {
                'description': 'Manage pets',
                'name': 'main',
                'operations': [
                    {
                        'function': 'create_pets',
                        'help': 'Create a pet',
                        'method': 'POST',
                        'name': 'add',
                        'operationId': 'createPets',
                        'path': '/pets'
                    },
                    {
                        'function': 'delete_pet_by_id',
                        'help': 'Delete a pet',
                        'method': 'DELETE',
                        'name': 'delete',
                        'operationId': 'deletePetById',
                        'path': '/pets/{petId}'
                    },
                    {
                        'function': 'list_pets',
                        'help': 'List all pets',
                        'method': 'GET',
                        'name': 'list',
                        'operationId': 'listPets',
                        'path': '/pets'
                    },
                    {
                        'function': 'show_pet_by_id',
                        'help': 'Info for a specific pet',
                        'method': 'GET',
                        'name': 'show',
                        'operationId': 'showPetById',
                        'path': '/pets/{petId}'
                    }
                ]
            },
            id="single",
        ),
        pytest.param(
            "pet2.yaml",
            "layout_pets2.yaml",
            {
                'description': 'Pet management application',
                 'name': 'main',
                 'operations': [
                    {'name': 'owners', 'subcommandId': 'owners'},
                    {'name': 'pet', 'subcommandId': 'pets'},
                    {'name': 'vets', 'subcommandId': 'veterinarians'},
                ]
            },
            id="subcommands",
        )
    ]
)
def test_tree_data(oas_filename, layout_filename, expected):
    oas = open_oas(asset_filename(oas_filename))
    uut = CliGenerator("cli", oas)
    node = file_to_tree(asset_filename(layout_filename))

    result = uut.tree_data(node)
    assert expected == result


@pytest.mark.parametrize(
    ["oas_filename", "layout_filename", "tree_filename"],
    [
        pytest.param("pet2.yaml", "layout_pets.yaml", "tree_pets.yaml", id="simple"),
        pytest.param("ct.yaml", "layout_cloudtruth.yaml", "tree_cloudtruth.yaml", id="nested"),
    ]
)
def test_tree_yaml(oas_filename, layout_filename, tree_filename):
    oas = open_oas(asset_filename(oas_filename))
    uut = CliGenerator("cli", oas)
    node = file_to_tree(asset_filename(layout_filename))
    expected = Path(asset_filename(tree_filename)).read_text()
    assert expected == uut.get_tree_yaml(node)


def test_tree_function():
    node = LayoutNode("bar", "foo_bar")
    uut = CliGenerator("cli", {})

    text = uut.tree_function(node)
    assert '@app.command("commands", short_help="Display commands tree for bar sub-commands")' in text
    assert 'def show_commands' in text
    assert '"""Show bar sub-commands.' in text
    assert 'display: _a.TreeDisplayOption = _a.TreeDisplay.HELP' in text
    assert 'depth: _a.MaxDepthOption = 5' in text
    assert '_t.tree(path.as_posix(), "foo_bar", display, depth)' in text
