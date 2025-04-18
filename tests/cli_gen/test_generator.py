from datetime import datetime
from datetime import timezone

import pytest

from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import file_to_tree
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
        pytest.param({SUM: "Short summary"}, "Short summary", id="summary-only"),
        pytest.param({SUM: "Short summary", DESC: "Short description"}, "Short description", id="desc-preferred"),
        pytest.param({DESC: "Short"}, "Short", id="short-desc"),
        pytest.param({DESC: "First.sentence ends. here"}, "First.sentence ends. here", id="long-desc"),
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


def test_op_infra_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    lines = uut.op_infra_arguments(op)
    text = "\n".join(lines)

    # check standard arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text
    assert "_api_timeout: _a.ApiTimeoutOption" in text
    assert "_log_level: _a.LogLevelOption" in text
    assert "_out_fmt: _a.OutputFormatOption" in text
    assert "_out_style: _a.OutputStyleOption" in text

    # check that we got the correct default server
    assert '= "http://petstore.swagger.io/v1"' in text


def test_op_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)

    text = uut.op_arguments(op)
    # check a couple infra arguments
    assert "_api_host: _a.ApiHostOption" in text
    assert "_api_key: _a.ApiKeyOption" in text

    # check a couple path parameter arguments
    assert 'num_feet: Annotated' in text
    assert 'your_boat: Annotated' in text

    # check a couple query parameter arguments
    assert 'situation: Annotated' in text
    assert 'more: Annotated' in text

    # check a couple body params
    assert 'name: Annotated[str,' in text
    assert 'tag: Annotated[Optional[str]' in text


def test_function_definition():
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

    # check the body of the function
    assert "_l.init_logging(_log_level)" in text
    assert "headers = _r.request_headers(_api_key)" in text
    assert 'url = _r.create_url(_api_host, "pets")' in text
    assert 'params = {}' in text
    assert 'data = _r.request("POST", url, headers=headers, params=params, timemout=_api_timeout)' in text
    assert '_d.display(data, _out_fmt, _out_style)' in text
    assert '_e.handle_exceptions(ex)' in text


def test_main():
    uut = Generator("cli_package", {})
    text = uut.main()
    assert 'if __name__ == "__main__":' in text
    assert "app()" in text
