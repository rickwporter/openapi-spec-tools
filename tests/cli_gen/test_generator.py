from copy import deepcopy
from pathlib import Path

import pytest

from openapi_spec_tools.cli_gen.generator import Generator
from openapi_spec_tools.cli_gen.layout import file_to_tree
from openapi_spec_tools.cli_gen.layout_types import LayoutNode
from openapi_spec_tools.cli_gen.layout_types import PaginationNames
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

def test_shebang():
    uut = Generator("cli_package", {})
    text = uut.shebang()
    assert text.startswith("#!/")
    assert "python3" in text


def test_standard_imports():
    uut = Generator("cli_package", {})
    text = uut.standard_imports()
    assert "import typer" in text
    assert "from typing import Annotated" in text


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
        pytest.param({SUM: "Summary has new  \nlines."}, "Summary has new", id="newline-summary"),
        pytest.param({SUM: "This has 'quotes'."}, r'This has \'quotes\'.', id="quotes-summary"),
        pytest.param({DESC: "Short"}, "Short", id="short-desc"),
        pytest.param({DESC: "First.sentence ends. here"}, "First.sentence ends", id="desc-sentence"),
        pytest.param({DESC: 'This has "quotes".'}, r'This has \"quotes\".', id="quotes-desc"),
        pytest.param({DESC: r"Contains \] slash"}, r"Contains \\] slash", id="slash"),
        pytest.param({DESC: "Description with\nin it."}, "Description with", id="newline-desc"),
    ]
)
def test_op_short_help(op, expected):
    uut = Generator("foo", {})
    assert expected == uut.op_short_help(op)


@pytest.mark.parametrize(
    ["op", "expected"],
    [
        pytest.param({}, "", id="empty"),
        pytest.param({SUM: "  \n "}, "", id="whitespace"),
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
        pytest.param(
            {DESC: 'Trailing whitespace  \t\nNext "line" with quotes'},
            """'''\n    Trailing whitespace\n    Next "line" with quotes\n    '''\n    """,
            id='multi-line-quotes',
        ),
        pytest.param(
            {DESC: 'First\n  Leading whitespace'},
            """'''\n    First\n      Leading whitespace\n    '''\n    """,
            id='multi-line-leading',
        ),
        pytest.param(
            {DESC: 'First\n\n  \n  After blanks'},
            """'''\n    First\n\n\n      After blanks\n    '''\n    """,
            id='multi-line-trailing',
        ),
        pytest.param(
            {DESC: 'First\n  This is more than the alloted 30 characters so will be wrapped\nnext line'},
            (
                "'''\n    First\n      This is more than the\n    alloted 30 characters "
                "so will\n    be wrapped\n    next line\n    '''\n    "
            ),
            id='wrapped-line',
        ),
        pytest.param(
            {DESC: 'Trailing blank lines  \t\n\t\n  \n '},
            """'''\n    Trailing blank lines\n    '''\n    """,
            id='blank-line-end',
        ),
        pytest.param(
            {DESC: '\n\t  \nLeading blank lines'},
            """'''\n    Leading blank lines\n    '''\n    """,
            id='blank-line-start',
        ),
    ]
)
def test_op_long_help(op, expected):
    uut = Generator("foo", {})
    uut.max_help_length = 30
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
    query_params = uut.op_params(op, "query")
    properties = uut.params_to_settable_properties(query_params)

    expected = """\
{}
    params["situation"] = situation
    if limit is not None:
        params["limit"] = limit
    if page_size is not None:
        params["page-size"] = page_size
    params["anotherQparam"] = another_qparam
    if more is not None:
        _l.logger().warning("--more is deprecated")
        params["more"] = more
    if day_value is not None:
        _l.logger().warning("--day-value was deprecated in last-release")
        params["dayValue"] = day_value
    if str_list_prop is not None:
        params["strListProp"] = str_list_prop
    if enum_with_default is not None:
        params["enumWithDefault"] = enum_with_default
    if str_enum_with_int_values is not None:
        params["strEnumWithIntValues"] = str_enum_with_int_values
    if type_ is not None:
        params["type"] = type_
    if param_with_enum_ref is not None:
        params["paramWithEnumRef"] = param_with_enum_ref
    if addr_street is not None:
        params["addr.street"] = addr_street
    if addr_city is not None:
        params["addr.city"] = addr_city
    if addr_state is not None:
        params["addr.state"] = addr_state
    params["addr.zipCode"] = addr_zip_code
    if favorite_day is not None:
        params["favoriteDay"] = favorite_day
    if crazy_enum is not None:
        params["crazyEnum"] = crazy_enum
    if list_enum_def_list is not None:
        params["listEnumDefList"] = list_enum_def_list
    if list_int_enum is not None:
        params["listIntEnum"] = list_int_enum\
"""
    text = uut.op_param_formation(properties)
    assert expected == text


@pytest.mark.parametrize(
    ["schema", "fmt", "expected"],
    [
        pytest.param("boolean", None, "bool", id="boolean"),
        pytest.param("integer", None, "int", id="integer"),
        pytest.param("numeric", None, "float", id="numeric"),
        pytest.param("number", None, "float", id="number"),
        pytest.param("string", None, "str", id="str"),
        pytest.param("string", "date-time", "datetime", id="datetime"),
        pytest.param("string", "date", "date", id="date"),
        pytest.param("bool", "binary", None, id="non-type"),
        pytest.param("object", None, None, id="object"),
        pytest.param("array", None, None, id="array"),
    ]
)
def test_schema_to_type(schema, fmt, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)

    assert expected == uut.schema_to_type(schema, fmt)


@pytest.mark.parametrize(
    ["proposed", "expected"],
    [
        pytest.param("simple", "Simple", id="simple"),
        pytest.param("snake_case_value", "SnakeCaseValue", id="snake"),
        pytest.param("camelCaseValue", "CamelCaseValue", id="camel"),
        pytest.param("decimal.dot.value", "DecimalDotValue", id="dotted"),
        pytest.param("AlreadyClassName", "AlreadyClassName", id="class"),
        pytest.param("dash-or-bash", "DashOrBash", id="dash"),
        pytest.param("space included", "SpaceIncluded", id="space"),
        pytest.param("more%special<chars:that>cause;problems", "MoreSpecialCharsThatCauseProblems", id="more"),
        pytest.param(
            "some{brace}and[bracket]and(paren)testing",
            "SomeBraceAndBracketAndParenTesting",
            id="parens",
        ),
        # these are the items that conflict with builtins
        pytest.param("any", "Any", id="any"),
        pytest.param("input", "Input", id="input"),
        pytest.param("list", "List", id="list"),
        pytest.param("@foo@&bar", "FooBar", id="pep-underscore"),
    ]
)
def test_class_name(proposed, expected):
    uut = Generator("cli_package", {})
    assert expected == uut.class_name(proposed)


@pytest.mark.parametrize(
    ["proposed", "expected"],
    [
        pytest.param("simple", "simple", id="simple"),
        pytest.param("snake_case_value", "snake_case_value", id="snake"),
        pytest.param("camelCaseValue", "camel_case_value", id="camel"),
        pytest.param("decimal.dot.value", "decimal_dot_value", id="dotted"),
        pytest.param("users/list", "users_list", id="slash"),
        pytest.param("dash-or-bash", "dash_or_bash", id="dash"),
        pytest.param("space included", "space_included", id="space"),
        pytest.param("more%special<chars:that>cause;problems", "more_special_chars_that_cause_problems", id="more"),
        pytest.param(
            "some{brace}and[bracket]and(paren)testing",
            "some_brace_and_bracket_and_paren_testing",
            id="parens",
        ),
        # these are the items that conflict with builtins
        pytest.param("any", "any_", id="any"),
        pytest.param("input", "input_", id="input"),
        pytest.param("list", "list_", id="list"),
    ],
)
def test_function_name(proposed, expected):
    uut = Generator("", {})
    assert expected == uut.function_name(proposed)


@pytest.mark.parametrize(
    ["proposed", "expected"],
    [
        pytest.param("simple", "simple", id="simple"),
        pytest.param("snake_case_value", "snake_case_value", id="snake"),
        pytest.param("camelCaseValue", "camel_case_value", id="camel"),
        pytest.param("decimal.dot.value", "decimal_dot_value", id="dotted"),
        pytest.param("users/list", "users_list", id="slash"),
        pytest.param("page-name", "page_name", id="dash"),
        pytest.param("space included", "space_included", id="space"),
        pytest.param("more%special<chars:that>cause;problems", "more_special_chars_that_cause_problems", id="more"),
        pytest.param(
            "some{brace}and[bracket]and(paren)testing",
            "some_brace_and_bracket_and_paren_testing",
            id="parens",
        ),
        # these are the items that conflict with builtins
        pytest.param("any", "any_", id="any"),
        pytest.param("input", "input_", id="input"),
        pytest.param("list", "list_", id="list"),
    ],
)
def test_variable_name(proposed, expected):
    uut = Generator("", {})
    assert expected == uut.variable_name(proposed)


@pytest.mark.parametrize(
    ["proposed", "expected"],
    [
        pytest.param("simple", "--simple", id="simple"),
        pytest.param("snake_case_value", "--snake-case-value", id="snake"),
        pytest.param("camelCaseValue", "--camel-case-value", id="camel"),
        pytest.param("decimal.dot.value", "--decimal-dot-value", id="dotted"),
        pytest.param("users/list", "--users-list", id="slash"),
        pytest.param("page-name", "--page-name", id="dash"),
        pytest.param("space included", "--space-included", id="space"),
        pytest.param("more%special<chars:that>cause;problems", "--more-special-chars-that-cause-problems", id="more"),
        pytest.param(
            "some{brace}and[bracket]and(paren)testing",
            "--some-brace-and-bracket-and-paren-testing",
            id="parens",
        ),
        # these are the items that conflict with builtins
        pytest.param("any", "--any", id="any"),
        pytest.param("input", "--input", id="input"),
        pytest.param("list", "--list", id="list"),
    ],
)
def test_option_name(proposed, expected):
    uut = Generator("", {})
    assert expected == uut.option_name(proposed)


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        pytest.param(None, None, id="none"),
        pytest.param("foo", "foo", id="str"),
        pytest.param({"sna": "foo"}, {"sna": "foo"}, id="dict"),
        pytest.param(["sna", "foo"], "sna", id="list-no-null"),
        pytest.param(["null", "sna"], "sna", id="list-null"),
        pytest.param(1, None, id="error"),
    ]
)
def test_simplify_type(schema, expected):
    uut = Generator("", {})
    assert expected == uut.simplify_type(schema)

@pytest.mark.parametrize(
    ["param_data", "expected"],
    [
        pytest.param({}, None, id="unknown"),
        pytest.param({TYPE: "string"}, "str", id="str"),
        pytest.param({TYPE: "integer"}, "int", id="int"),
        pytest.param({TYPE: "numeric"}, "float", id="float"),
        pytest.param({TYPE: "string", ENUM: ["a", "b"], "name": "sna_foo"}, "SnaFoo", id="unref-enum"),
        pytest.param(
            {TYPE: "string", ENUM: ["a", "b"], "$ref": "#/comp/Schema/FooBar", "name": "sna_foo"},
            "SnaFoo",
            id="ref-enum",
        ),
    ],
)
def test_get_parameter_pytype(param_data, expected):
    uut = Generator("cli_package", {})
    assert expected == uut.get_parameter_pytype(param_data)


@pytest.mark.parametrize(
    ["prop_name", "prop_data", "expected"],
    [
        pytest.param("foo", {TYPE: "string", REQUIRED: True}, "str", id="str"),
        pytest.param("foo", {TYPE: "string", FORMAT: "date-time", REQUIRED: True}, "datetime", id="datetime"),
        pytest.param("foo", {TYPE: "string", FORMAT: "unknown", REQUIRED: False}, "Optional[str]", id="optional-str"),
        pytest.param("foo", {TYPE: "integer"}, "Optional[int]", id="optional-int"),
        pytest.param(
            "foo",
            {TYPE: "string", FORMAT: "date", COLLECT: "array", REQUIRED: True},
            "list[date]",
            id="list-date",
        ),
        pytest.param(
            "foo",
            {TYPE: "numeric", COLLECT: "array", REQUIRED: False},
            "Optional[list[float]]",
            id="optional-list-float",
        ),
        pytest.param("foo", {TYPE: "foo"}, None, id="unknown"),
        pytest.param(
            "foo",
            {TYPE: "string", REQUIRED: True, ENUM: ["a", "b"], "x-reference": "east_west"},
            "Foo",
            id="named-enum",
        ),
        pytest.param(
            "foo",
            {TYPE: "string", REQUIRED: True, ENUM: ["a", "b"]},
            "Foo",
            id="unnamed-enum"
        ),
    ],
)
def test_get_property_pytype(prop_name, prop_data, expected):
    uut = Generator("cli_package", {})
    assert expected == uut.get_property_pytype(prop_name, prop_data)


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
    body_params = uut.op_body_settable_properties(op)
    text = uut.op_body_formation(body_params)
    assert "body = {}" in text
    assert 'body["id"]' not in text  # ignore read-only
    assert 'body["name"] = name' in text  # required
    assert 'if another_value is not None:' in text  # not required, so check if not None
    assert '_l.logger().warning("--another-value is deprecated and should not be used")' in text
    assert 'body["anotherValue"] = another_value' in text  # check prop vs variable name
    assert 'if bogus is not None:' not in text
    assert 'if optional_list is not None:' in text
    assert 'body["optionalList"] = optional_list' in text
    assert 'if first_choice is not None:' in text
    assert 'body["firstChoice"] = first_choice' in text
    assert 'if list_various is not None:' in text
    assert 'body["listVarious"] = list_various' in text
    assert 'body["format"] = format_' in text
    assert 'if gone is not None:' in text
    assert '_l.logger().warning("--gone was deprecated in 5.6 and should not be used")' in text
    assert 'body["gone"] = gone' in text
    assert 'if best_day is not None' in text
    assert 'body["bestDay"] = best_day' in text
    assert 'if inconsistent is not None' in text
    assert 'body["inconsistent"] = inconsistent' in text

    # this is for the sub-object -- just check the infra and a couple properties
    assert 'owner = {}' in text
    assert 'home = {}' in text
    assert 'if owner_home_street is not None' in text
    assert 'home["street"] = owner_home_street' in text
    assert 'if owner_home_zip_code is not None' in text
    assert 'home["zipCode"] = owner_home_zip_code' in text
    assert 'if home:' in text
    assert 'owner["home"] = home' in text
    assert 'if owner:' in text
    assert 'body["owner"] = owner' in text

    # make sure sub-object is populated before checking if it is populated
    assert text.find('if home:') < text.find('if owner:')


def test_op_path_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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


@pytest.mark.parametrize(
    ["reference", "expected"],
    [
        pytest.param("Species", False, id="enum"),
        pytest.param("AllOfSpecies", False, id="all-of-enum"),
        pytest.param("RefToSpecies", False, id="ref-to-enum"),
        pytest.param("SpeciesProp", False, id="single-enum-prop"),
        pytest.param("Pet", True, id="obj"),
        pytest.param("PetInherited", True, id="obj-inherted"),
        pytest.param("PetReference", True, id="obj-reference"),
    ]
)
def test_model_is_complex(reference, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)
    model = uut.get_model(f"#/components/schemas/{reference}")
    assert expected == uut.model_is_complex(model)


@pytest.mark.parametrize(
    ["enum_type", "values", "expected"],
    [
        pytest.param('string', [1, "*"], True, id="str-match"),
        pytest.param('integer', [-1, 0, 1, 2, 3], True, id="int-match"),
        pytest.param('integer', [-1, 0.1, 1, 2, 3], False, id="int-diff"),
        pytest.param('numeric', [-1, 0, 1, 2, 3.14159], True, id="float-match"),
        pytest.param('numeric', [-1, 0.1, 1, 2, 3, '*'], False, id="float-diff"),
        pytest.param('boolean', [True, False, True, True], True, id='bool-match'),
        pytest.param('boolean', [False, 0, True], False, id="bool-diff")
    ]
)
def test_enum_values_match_type(enum_type, values, expected):
    uut = Generator("cli_package", {})
    assert expected == uut.enum_values_match_type(enum_type, values)

SIMPLE_ENUM = """\
class Simple(str, Enum):  # noqa: F811
    A_OR_B = "aOrB"
    B_OR_C = "b_or_C"
    _MINUS = "-minus"

"""

NUMBER_ENUM = """\
class SimpleNumber(int, Enum):  # noqa: F811
    VALUE_12 = 12
    VALUE_37 = 37
    VALUE_11 = 11

"""

NON_STR_ENUM = """\
class anyThing_goes(int, Enum):  # noqa: F811
    VALUE_1 = 1
    VALUE_NONE = None
    VALUE_TRUE = True

"""
MIXED_ENUM = """\
class MixedValues(str, Enum):  # noqa: F811
    VALUE_A = "a"
    VALUE_1 = "1"
    VALUE_TRUE = "True"
    VALUE_B = "b"
"""
INT_STR_ENUM = """\
class IntStrings(str, Enum):  # noqa: F811
    VALUE_10 = "10"
    VALUE_10_1 = "10.1"
"""
CASE_SENSE_ENUM = """\
class Sna(str, Enum):  # noqa: F811
    FOO0 = "foo"
    FOO1 = "FOO"

"""
SPECIAL_ENUM = """\
class Special(str, Enum):  # noqa: F811
    _TIME0 = "-time"
    _TIME1 = "+time"

"""

SIMPLE_PARAM = {
    TYPE: "string",
    ENUM: ["aOrB", "b_or_C", "-minus"], "$ref": "#/components/schemas/Simple",
    "name": "simple",
}

NUMBER_PARAM = {TYPE: "integer", ENUM: [12, 37, 11], "name": "simple-number"}
MIXED_PARAM = {TYPE: "string", ENUM: ["a", 1, True, "b"], "name": "mixed-values"}
INT_STR_PARAM = {TYPE: "string", ENUM: ["10", "10.1"], "name": "int-strings"}
SIMPLE_PROP = deepcopy(SIMPLE_PARAM)
SIMPLE_PROP[DEF] = None

@pytest.mark.parametrize(
    ["name", "enum_type", "values", "expected"],
    [
        pytest.param("Simple", "str", ["aOrB", "b_or_C", "-minus"], SIMPLE_ENUM, id="str"),
        pytest.param("anyThing_goes", "int", [1, None, True], NON_STR_ENUM, id="non-str"),
        pytest.param("Sna", "str", ["foo", "FOO"], CASE_SENSE_ENUM, id="case-sense"),
        pytest.param("Special", "str", ["-time", "+time"], SPECIAL_ENUM, id="special"),
    ]
)
def test_enum_declaration(name, enum_type, values, expected):
    uut = Generator("", {})
    declaration = uut.enum_declaration(name, enum_type, values)
    assert expected == declaration


@pytest.mark.parametrize(
    ["path_params", "query_params", "body_params", "expected"],
    [
        pytest.param([], [], {}, "", id="empty"),
        pytest.param(
            [SIMPLE_PARAM],
            [],
            {},
            f"\n{SIMPLE_ENUM}",
            id="ref-path",
        ),
        pytest.param(
            [],
            [SIMPLE_PARAM],
            {},
            f"\n{SIMPLE_ENUM}",
            id="ref-query",
        ),
        pytest.param(
            [NUMBER_PARAM],
            [],
            {},
            f"\n{NUMBER_ENUM}",
            id="number",
        ),
        pytest.param(
            [],
            [],
            {"simple": {TYPE: "string", ENUM: ["aOrB", "b_or_C", "-minus"], "x-reference": "Simple"}},
            f"\n{SIMPLE_ENUM}",
            id="ref-body",
        ),
        pytest.param(
            [SIMPLE_PARAM],
            [SIMPLE_PARAM],
            {"simple": {TYPE: "string", ENUM: ["aOrB", "b_or_C", "-minus"], "x-reference": "Simple"}},
            f"\n{SIMPLE_ENUM}",
            id="de-dup",
        ),
        pytest.param(
            [],
            [MIXED_PARAM],
            {},
            f"\n{MIXED_ENUM}\n",
            id="mixed",
        ),
        pytest.param(
            [],
            [INT_STR_PARAM],
            {},
            f"\n{INT_STR_ENUM}\n",
            id="int-str"
        )
    ],
)
def test_enum_definitions(path_params, query_params, body_params, expected):
    uut = Generator("", {})
    definitions = uut.enum_definitions(path_params, query_params, body_params)
    assert expected == definitions


@pytest.mark.parametrize(
    ["parameter", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param(SIMPLE_PARAM, SIMPLE_PROP, id="simple"),
        pytest.param(
            {ONE_OF: [{TYPE: "foo"}, {TYPE: "array", ITEMS: {TYPE: "foo"}}]},
            {TYPE: "foo", COLLECT: "array"},
            id="oneOf-collect-match"
        ),
        pytest.param(
            {ONE_OF: [{TYPE: "foo"}, {TYPE: "array", ITEMS: {TYPE: "bar"}}]},
            {TYPE: "foo"},
            id="oneOf-collect-diff"
        ),
        pytest.param(
            {TYPE: ["foo", "null"]},
            {TYPE: "foo", REQUIRED: False},
            id="nullable"
        ),
        pytest.param(
            {ANY_OF: [{TYPE: "array", ITEMS: {TYPE: "sna"}}, {TYPE: "foo"}]},
            {TYPE: "sna", COLLECT: "array"},
            id="anyOf"
        ),
        pytest.param(
            # enum and default values converted to strings
            {TYPE: "array", ITEMS: {ENUM: ['*', 0], DEF: 0, TYPE: 'string'}},
            {TYPE: "string", COLLECT: "array", ENUM: ['*', '0'], DEF: '0'},
            id="enum-str-list",
        ),
        pytest.param(
            # enum and default values stay as integers
            {TYPE: "array", ITEMS: {TYPE: "integer", ENUM: [1, 5, 9], DEF: 5}},
            {TYPE: "integer", COLLECT: "array", ENUM: [1, 5, 9], DEF: 5},
            id="enum-int-list",
        ),
        pytest.param(
            # multiple types converted to string for compatability, and enum/default values converted
            {TYPE: ["integer", "string"], ENUM: ['*', 1, 3], DEF: 1},
            {TYPE: "string", ENUM: ['*', '1', '3'], DEF: '1'},
            id="enum-multi-type",
        ),
        pytest.param(
            # default value list converted to strings
            {TYPE: "array", ITEMS: {TYPE: ["integer", "string"], ENUM: ["-inf", "pi", 3], DEF: ["pi", 3]}},
            {TYPE: "string", ENUM: ["-inf", "pi", "3"], COLLECT: "array", DEF: ["pi", "3"]},
            id="enum-list-default"
        )
    ],
)
def test_param_to_property(parameter, expected):
    uut = Generator("", {})
    prop = uut.param_to_property(parameter)
    assert expected == prop


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
                    'x-parents': ['home'],
                    'x-field': 'street',
                },
                'home.city': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-parents': ['home'],
                    'x-field': 'city',
                },
                'home.state': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-field': 'state',
                    'x-parents': ['home'],
                },
                'home.zipCode': {
                    'type': 'string',
                    'required': False,
                    'x-reference': 'Address',
                    'x-field': 'zipCode',
                    'x-parents': ['home'],
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
                'type': {
                    'enum': ['FeatureCollection'],
                    'type': 'string',
                    'required': True,
                    'x-reference': 'GeoJsonFeatureCollection',
                    'x-field': 'type',
                },
                'pagination.next':
                {
                    'description': 'A link to the next page of records',
                    'format': 'uri',
                    'required': False,
                    'type': 'string',
                    'x-field': 'next',
                    'x-parents': ['pagination'],
                    'x-reference': 'PaginationInfo',
                },
                'observationStations': {
                    'type': 'string',
                    'format': 'uri',
                    'required': False,
                    'x-collection': 'array',
                    'x-field': 'observationStations'
                },
            },
            id="allOf-multi"
        ),
        pytest.param(
            "MultipleAnyOf",
            {
                'anotherValue': {
                    'default': 'Anything goes',
                    'deprecated': True,
                    'description': 'A string with a default',
                    'required': False,
                    'type': 'string',
                    'x-reference': 'Pet',
                },
                'name': {
                    'description': 'Pet name',
                    'required': True,
                    'type': 'string',
                    'x-reference': 'Pet',
                },
                'tag': {
                    'description': 'Pet classification',
                    'required': False,
                    'type': 'string',
                    'x-reference': 'Pet',
                },
            },
            id="anyOf-multi",
        ),
        pytest.param(
            "GeoJsonFeatureCollection",
            {
                'type': {
                    'enum': ['FeatureCollection'],
                    'type': 'string',
                    'required': True,
                },
            },
            id="unnested",
        ),
        pytest.param(
            "DeeperNesting",
            {
                'observationStations': {
                    'type': 'string',
                    'format': 'uri',
                    'required': False,
                    'x-field': 'observationStations',
                    'x-reference': 'ObservationStationCollectionGeoJson',
                    'x-collection': 'array',
                },
                'owner.home.city': {
                    'required': False,
                    'type': 'string',
                    'x-field': 'city',
                    'x-parents': ['owner', 'home'],
                    'x-reference': 'Address',
                },
                'owner.home.state': {
                    'required': False,
                    'type': 'string',
                    'x-field': 'state',
                    'x-parents': ['owner', 'home'],
                    'x-reference': 'Address',
                },
                'owner.home.street': {
                    'description': 'Street address (e.g. 123 Main Street, POBox 507)',
                    'required': False,
                    'type': 'string',
                    'x-field': 'street',
                    'x-parents': ['owner', 'home'],
                    'x-reference': 'Address',
                },
                'owner.home.zipCode': {
                    'required': False,
                    'type': 'string',
                    'x-field': 'zipCode',
                    'x-parents': ['owner', 'home'],
                    'x-reference': 'Address',
                },
                'owner.iceCream': {
                    'description': 'Favorite ice cream flavor',
                    'required': False,
                    'type': 'string',
                    'x-field': 'iceCream',
                    'x-parents': ['owner'],
                    'x-reference': 'Owner',
                },
                'owner.name': {
                    'descrption': 'Name of the pet owner',
                    'required': False,
                    'type': 'string',
                    'x-field': 'name',
                    'x-parents': ['owner'],
                    'x-reference': 'Person',
                },
                'pagination.next': {
                    'description': 'A link to the next page of records',
                    'format': 'uri',
                    'required': False,
                    'type': 'string',
                    'x-field': 'next',
                    'x-parents': ['pagination'],
                    'x-reference': 'PaginationInfo',
                },
                'type': {
                    'enum': ['FeatureCollection'],
                    'required': False,
                    'type': 'string',
                    'x-field': 'type',
                    'x-reference': 'GeoJsonFeatureCollection',
                },
            },
            id="nesting",
        ),
        pytest.param(
            "Attachment",
            {
                'bytes': {'nullable': True, 'required': False, 'type': 'string'},
                'date': {'format': 'date', 'required': False, 'type': 'string'},
                'edgeColor': {
                    'enum': ['yellow', 'purple', 'blue'],
                    'nullable': True,
                    'required': False,
                    'type': 'string',
                    '$ref': '#/components/schemas/Color',
                    'x-reference': 'Color',
                },
                'id': {
                    'pattern': '^[0-9a-fA-F]{24}$',
                    'type': 'string',
                    'required': False,
                    '$ref': '#/components/schemas/TrelloID',
                    'x-reference': 'TrelloID',
                },
                'idMember': {'required': False, 'type': 'string'},
                'isUpload': {'required': False, 'type': 'boolean'},
                'mimeType': {'required': False, 'type': 'string'},
                'name': {'required': False, 'type': 'string'},
                'pos': {'format': 'float', 'required': False, 'type': 'number'},
                'previews': {'type': 'string', 'required': False, 'x-collection': 'array'},
                'url': {'format': 'url', 'required': False, 'type': 'string'}
            },
            id="item"
        ),
        pytest.param(
            "MultiAttachmentProperties",
            {
                'color': {
                    'type': 'string',
                    'enum': ['yellow', 'purple', 'blue'],
                    'required': False,
                    'nullable': True,
                    'x-field': 'color',
                    'x-reference': 'Color',
                    '$ref': '#/components/schemas/Color',
                },
            },
            id="list-all-of"
        ),
        pytest.param(
            "MultiAttachmentList",
            {},
            id="list-ref",
        ),
        pytest.param(
            "EnumListProperty",
            {
                'rainbow': {
                    '$ref': '#/components/schemas/Color',
                    'type': 'string',
                    'enum': ['yellow', 'purple', 'blue'],
                    'required': True,
                    'nullable': True,
                    'x-reference': 'Color',
                    'x-collection': 'array',
                }
            },
            id="list-enum",
        ),
        pytest.param(
            "MissingInheritedSubmodel",
            {'sna': {'type': 'string', 'required': True}},
            id="missing-submodel",
        ),
        pytest.param(
            "MissingSubmodelProperty",
            {'bar': {'type': 'string', 'required': False}},
            id="missing-submodel",
        ),
        pytest.param(
            "MissingItemsModel",
            {'foo': {'type': 'integer', 'required': False}},
            id="missing-items",
        ),
        pytest.param(
            "MembershipCreate",
            {
                'role': {
                    'enum': ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    'required': True,
                    'type': 'string',
                    'x-reference': 'RoleEnum',
                    '$ref': '#/components/schemas/RoleEnum',
                    'description': 'The role that the user has in the organization.',
                },
                'user': {
                    'description': 'The user of the membership.',
                    'format': 'uri',
                    'required': True,
                    'type': 'string',
                },
            },
            id="enum-all-of"
        ),
        pytest.param(
            "MembershipCreateAnyOf",
            {
                'role': {
                    'enum': ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    'required': False,
                    'type': 'string',
                    'x-reference': 'RoleEnum',
                    '$ref': '#/components/schemas/RoleEnum',
                    'description': 'The role that the user has in the organization.',
                },
            },
            id="enum-any-of"
        ),
        pytest.param(
            "MembershipCreateOneOf",
            {
                'role': {
                    'enum': ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    'required': False,
                    'type': 'string',
                    'x-reference': 'RoleEnum',
                    '$ref': '#/components/schemas/RoleEnum',
                    'description': 'The role that the user has in the organization.',
                },
            },
            id="enum-one-of"
        ),
    ]
)
def test_model_settable_properties(model_name, expected):
    oas = open_oas(asset_filename("misc.yaml"))
    uut = Generator("cli_package", oas)
    model = uut.get_model(f"#/components/schemas/{model_name}")
    properties = uut.model_settable_properties(model_name, model)
    assert expected == properties


def test_op_body_arguments():
    oas = open_oas(asset_filename("misc.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = Generator("cli_package", oas)
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
    uut = Generator("foo", {})
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
    uut = Generator("cli_package", oas)

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
    uut = Generator("cli_package", oas)
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
    uut = Generator("foo", {})

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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", oas)
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
    uut = Generator("cli_package", {})
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
    uut = Generator("cli", oas)
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
    uut = Generator("cli", oas)
    node = file_to_tree(asset_filename(layout_filename))
    expected = Path(asset_filename(tree_filename)).read_text()
    assert expected == uut.get_tree_yaml(node)


def test_tree_function():
    node = LayoutNode("bar", "foo_bar")
    uut = Generator("cli", {})

    text = uut.tree_function(node)
    assert '@app.command("commands", short_help="Display commands tree for bar sub-commands")' in text
    assert 'def show_commands' in text
    assert '"""Show bar sub-commands.' in text
    assert 'display: _a.TreeDisplayOption = _a.TreeDisplay.HELP' in text
    assert 'depth: _a.MaxDepthOption = 5' in text
    assert '_t.tree(path.as_posix(), "foo_bar", display, depth)' in text
