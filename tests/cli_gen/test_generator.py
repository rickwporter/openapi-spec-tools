from datetime import datetime
from datetime import timezone

import pytest

from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.cli_gen.layout_types import CommandNode
from oas_tools.cli_gen.layout_types import PaginationNames
from oas_tools.types import OasField
from oas_tools.utils import map_operations
from oas_tools.utils import open_oas
from tests.helpers import asset_filename

SUM = "summary"
DESC = "description"


def test_shebang():
    uut = Generator("cli_package", {})
    text = uut.shebang()
    assert text.startswith("#!/")
    assert "python3" in text


def test_copyright():
    uut = Generator("cli_package", {})
    year = datetime.now(timezone.utc).year
    text = uut.copyright()
    assert "Copyright" in text
    assert str(year) in text


def test_standard_imports():
    uut = Generator("cli_package", {})
    text = uut.standard_imports()
    assert "import typer" in text
    assert "from typing_extensions import Annotated" in text


def test_subcommand_imports():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = Generator("cli_package", oas)
    text = uut.subcommand_imports(tree.subcommands())
    for name in ["pets", "owners", "veterinarians"]:
        line = f"from cli_package.{name} import app as {name}"
        assert line in text


def test_app_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = Generator("cli_package", oas)
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


@pytest.mark.parametrize(
    ["op", "expected"],
    [
        pytest.param({}, "", id="empty"),
        pytest.param({SUM: "Short summary"}, "Short summary", id="summary-only"),
        pytest.param({SUM: "Short summary", DESC: "Short description"}, "Short summary", id="summary-preferred"),
        pytest.param({SUM: "Summary does NOT. Get truncated."}, "Summary does NOT. Get truncated.", id="long-summary"),
        pytest.param({DESC: "Short"}, "Short", id="short-desc"),
        pytest.param({DESC: "First.sentence ends. here"}, "First.sentence ends", id="desc-sentence"),
    ]
)
def test_op_short_help(op, expected):
    uut = Generator("foo", {})
    assert expected == uut.op_short_help(op)


@pytest.mark.parametrize(
    ["op", "expected"],
    [
        pytest.param({}, "", id="empty"),
        pytest.param(
            {SUM: "Short summary"},
            "'''\n    Short summary\n    '''\n    ",
            id="summary-only",
        ),
        pytest.param(
            {SUM: "Short summary", DESC: "Short description"},
            "'''\n    Short description\n    '''\n    ",
            id="desc-preferred",
        ),
        pytest.param(
            {DESC: "Short"},
            "'''\n    Short\n    '''\n    ",
            id="short-desc",
        ),
        pytest.param(
            {DESC: "First.sentence ends. here"},
            "'''\n    First.sentence ends. here\n    '''\n    ",
            id="long-desc",
        ),
    ]
)
def test_op_long_help(op, expected):
    uut = Generator("foo", {})
    assert expected == uut.op_long_help(op)


@pytest.mark.parametrize(
    ["path", "expected"],
    [
        pytest.param('foo', '_api_host, "foo"', id="foo"),
        pytest.param('foo/bar', '_api_host, "foo/bar"', id="foo/bar"),
        pytest.param('foo/{bar}', '_api_host, "foo", bar', id="foo/{bar}"),
        pytest.param('sna/foo/bar', '_api_host, "sna/foo/bar"', id="sna/foo/bar"),
        pytest.param('sna/{foo}/bar', '_api_host, "sna", foo, "bar"', id="sna/{foo}/bar"),
    ]
)
def test_op_url_params(path, expected):
    uut = Generator("cli_package", {})
    assert expected == uut.op_url_params(path)


def test_op_param_formation():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    expected = """\
{}
    params["situation"] = situation
    if limit is not None:
        params["limit"] = limit
    params["anotherQparam"] = another_qparam
    if more is not None:
        params["more"] = more\
"""
    text = uut.op_param_formation(op)
    assert expected == text


@pytest.mark.parametrize(
    ["schema", "fmt", "expected"],
    [
        pytest.param("boolean", None, "bool", id="boolean"),
        pytest.param("integer", None, "int", id="integer"),
        pytest.param("numeric", None, "float", id="numeric"),
        pytest.param("string", None, "str", id="str"),
        pytest.param("string", "date-time", "datetime", id="datetime"),
    ]
)
def test_schema_to_type_success(schema, fmt, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)

    assert expected == uut.schema_to_type(schema, fmt)


@pytest.mark.parametrize(
    ["schema", "fmt"],
    [
        pytest.param("bool", "binary", id="non-type"),
        pytest.param("object", None, id="object"),  # TODO: handle object
        pytest.param("array", None, id="array"), # TODO: handle list
    ]
)
def test_schema_to_type_failure(schema, fmt):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)

    with pytest.raises(ValueError, match=f"Unable to determine type for {schema}"):
        uut.schema_to_type(schema, fmt)


@pytest.mark.parametrize(
    ["op_id", "expected"],
    [
        pytest.param("deleteSomething", '', id="None"),
        pytest.param("testPathParams", ', content_type="application/json"', id="JSON"),
    ],
)
def test_op_content_type(op_id, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get(op_id)
    uut = Generator("cli_package", oas)

    assert expected == uut.op_content_header(op)


def test_op_body_formation():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)
    text = uut.op_body_formation(op)
    assert "body = {}" in text
    assert 'body["id"]' not in text  # ignore read-only
    assert 'body["name"] = name' in text  # required
    assert 'if another_value is not None:' in text  # not required, so check if not None
    assert 'body["anotherValue"] = another_value'  # check prop vs variable name

def test_op_path_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    lines = uut.op_path_arguments(op)
    text = "\n".join(lines)

    assert 'num_feet: Annotated[Optional[int], typer.Option(show_default=False, help="Number of feet")] = None' in text
    assert 'species: Annotated[str, typer.Option(help="Species name in Latin without spaces")] = "monkey"' in text
    assert 'neutered: Annotated[bool, typer.Option(help="Ouch")] = True' in text
    assert (
        'birthday: Annotated[Optional[datetime], typer.Option(show_default=False, help="When is the party?")] = None'
        in text
    )
    assert 'must_have: Annotated[str, typer.Argument(show_default=False, help="")]' in text
    assert 'your_boat: Annotated[float, typer.Option(help="Pi is always good")] = 3.14159' in text

    # make sure we ignore the query params
    assert 'situation: Annotated' not in text
    assert 'more: Annotated' not in text


def test_op_query_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    lines = uut.op_query_arguments(op)
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
        'another_qparam: Annotated[Optional[str], typer.Option(show_default=False, help="Query parameter")] = None'
        in text
    )
    assert 'more: Annotated[bool, typer.Option(help="")] = False' in text

    # make sure path params not included
    assert 'num_feet: Annotated' not in text
    assert 'must_have: Annotated' not in text

@pytest.mark.parametrize(
    ["model_name", "expected"],
    [
        pytest.param(
            "Owner",
            {
                'name': {
                    'descrption': 'Name of the pet owner',
                    'type': 'string',
                    'required': True,
                    'x-reference': 'Person',
                    'x-field': 'name',
                },
                'home.street': {
                    'description': 'Street address (e.g. 123 Main Street, POBox 507)',
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-parent': 'home',
                    'x-field': 'street',
                },
                'home.city': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-parent': 'home',
                    'x-field': 'city',
                },
                'home.state': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-field': 'state',
                    'x-parent': 'home',
                },
                'home.zipCode': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-field': 'zipCode',
                    'x-parent': 'home',
                },
                'iceCream': {
                    'type': 'string',
                    'description': 'Favorite ice cream flavor',
                    'required': False,
                }
            },
            id="Owner",
        ),
        pytest.param(
            "ObservationStationCollectionGeoJson",
            {
                '@context': {
                    '$ref': '#/components/schemas/JsonLdContext',
                    'required': False,
                    'x-reference': 'GeoJsonFeatureCollection',
                    'x-field': '@context',
                },
                'type': {
                    'enum': ['FeatureCollection'],
                    'type': 'string',
                    'required': True,
                    'x-reference': 'GeoJsonFeatureCollection',
                    'x-field': 'type',
                },
                # NOTE: this come from the later properties tha overrides the GeoJsonFeatureCollection
                'features': {
                    'items': {
                        'properties': {
                            'properties': {'$ref': '#/components/schemas/ObservationStation'}
                        },
                        'type': 'object',
                    },
                    'required': False,
                     'type': 'array',
                },
                'pagination': {
                    '$ref': '#/components/schemas/PaginationInfo',
                    'required': False,
                },
                'observationStations': {
                    'items': {'format': 'uri', 'type': 'string'},
                    'required': False,
                    'type': 'array',
                },
            },
            id="allOf-properties"
        ),
    ]
)
def test_expand_settable_properties(model_name, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)
    model = uut.get_reference_model(model_name)
    properties = uut.expand_settable_properties(model)
    assert expected == properties


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    lines = uut.op_body_arguments(op)
    text = "\n".join(lines)
    assert 'name: Annotated[str, typer.Option(show_default=False, help="Pet name")] = None' in text
    assert 'tag: Annotated[Optional[str], typer.Option(show_default=False, help="Pet classification")] = None' in text
    assert (
        'another_value: Annotated[Optional[str], typer.Option(show_default=False, '
        'help="A string with a default")] = "Anything goes"'
        in text
    )

    # make sure read-only not included
    assert 'id: Annotated' not in text


@pytest.mark.parametrize(
    ["names", "expected"],
    [
        pytest.param(None, "", id="None"),
        pytest.param(PaginationNames(), "page_info = _r.PageParams(max_count=_max_count)", id="empty"),
        pytest.param(
            PaginationNames(page_size="fooBar"),
            'page_info = _r.PageParams(max_count=_max_count, page_size_name="fooBar", page_size_value=foo_bar)',
            id="page_size",
        ),
        pytest.param(
            PaginationNames(page_start="snaFoo"),
            'page_info = _r.PageParams(max_count=_max_count, page_start_name="snaFoo", page_start_value=sna_foo)',
            id="page_start",
        ),
        pytest.param(
            PaginationNames(item_start="eastWest"),
            'page_info = _r.PageParams(max_count=_max_count, item_start_name="eastWest", item_start_value=east_west)',
            id="item_start",
        ),
        pytest.param(
            PaginationNames(items_property="northSouth"),
            'page_info = _r.PageParams(max_count=_max_count, item_property_name="northSouth")',
            id="items_property",
        ),
        pytest.param(
            PaginationNames(next_header="upDown"),
            'page_info = _r.PageParams(max_count=_max_count, next_header_name="upDown")',
            id="next_header",
        ),
        pytest.param(
            PaginationNames(next_property="leftRight"),
            'page_info = _r.PageParams(max_count=_max_count, next_property_name="leftRight")',
            id="next_property",
        ),
    ]
)
def test_pagination_creation(names, expected) -> None:
    node = CommandNode(command="foo", identifier="bar", pagination=names)
    uut = Generator("foo", {})
    result = uut.pagination_creation(node)
    assert expected == result.strip()

@pytest.mark.parametrize(
    ["command", "has_details"],
    [
        pytest.param(CommandNode("foo", "foo"), False, id="no-summary"),
        pytest.param(CommandNode("foo", "foo", summary_fields=["abc"]), True, id="summary"),
    ],
)
def test_op_infra_arguments(command, has_details):
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    lines = uut.op_infra_arguments(op, command)
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


def test_op_arguments():
    command = CommandNode(command="foo", identifier="bar", summary_fields=["123"])
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    text = uut.op_arguments(op, command)
    # check a couple infra arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text
    assert "_details: _a.DetailsOption" in text

    # check a couple path parameter arguments
    assert 'num_feet: Annotated' in text
    assert 'your_boat: Annotated' in text

    # check a couple query parameter arguments
    assert 'situation: Annotated' in text
    assert 'more: Annotated' in text

    # check a couple body params
    assert 'name: Annotated[str,' in text
    assert 'tag: Annotated[Optional[str]' in text


def test_op_check_missing():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    text = uut.op_check_missing(op)

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
    uut = Generator("foo", {})

    command = CommandNode("foo", "foo", summary_fields=["abc", "defGhi"])
    text = uut.summary_display(command)
    assert 'if not _details:' in text
    assert 'data = summary(data, ["abc", "defGhi"])' in text

    command = CommandNode("foo", "foo")
    text = uut.summary_display(command)
    assert '' == text


def test_function_definition_item():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = Generator("cli_package", oas)
    text = uut.function_definition(item)
    assert '@app.command("create", help="Create a pet")' in text
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
    assert 'data = _r.request("POST", url, headers=headers, params=params, body=body, timemout=_api_timeout)' in text
    assert '_d.display(data, _out_fmt, _out_style)' in text
    assert '_e.handle_exceptions(ex)' in text
    assert 'data = _d.summary(data, "name")'

    # make sure the missing parameter checks are present
    assert 'missing.append("--api-key")'
    assert 'missing.append("--name")'
    assert ' _e.handle_exceptions(_e.MissingRequiredError(missing))' in text


def test_function_definition_paged():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets.yaml"))
    item = tree.find("list")
    uut = Generator("cli_package", oas)
    text = uut.function_definition(item)

    assert '@app.command("list", help="List all pets")' in text
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
    assert 'page_info = _r.PageParams(max_count=_max_count, page_size_name="limit", page_size_value=limit)' in text
    assert 'data = _r.depaginate(page_info, url, headers=headers, params=params, timemout=_api_timeout)' in text


def test_main():
    uut = Generator("cli_package", {})
    text = uut.main()
    assert 'if __name__ == "__main__":' in text
    assert "app()" in text
