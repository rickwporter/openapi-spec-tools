from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.base_gen.base_generator import DEFAULT_COPYRIGHT
from openapi_spec_tools.base_gen.base_generator import BaseGenerator
from openapi_spec_tools.base_gen.config import GeneratorConfig
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.constants import ADDITIONAL_PROPS
from tests.constants import ANY_OF
from tests.constants import COLLECT
from tests.constants import DEF
from tests.constants import DEPRECATED
from tests.constants import DESC
from tests.constants import ENUM
from tests.constants import FORMAT
from tests.constants import ITEMS
from tests.constants import NAME
from tests.constants import NULLABLE
from tests.constants import ONE_OF
from tests.constants import PROPS
from tests.constants import REFS
from tests.constants import REQUIRED
from tests.constants import SINGLE
from tests.constants import SUM
from tests.constants import TYPE
from tests.constants import X_ENUM
from tests.constants import X_FIELD
from tests.constants import X_PARENTS
from tests.constants import X_REF
from tests.helpers import asset_filename

S1 = '\n    '
S2 = f"{S1}    "
PKG = "some_package"


def test_package_name():
    assert "" == BaseGenerator(package_name="", oas={}).package_name
    assert "pets" == BaseGenerator(package_name="pets", oas={}).package_name


def test_copyright_text():
    assert DEFAULT_COPYRIGHT == BaseGenerator(oas={}, package_name=PKG).copyright

    text = "# this is my copyright\n"
    assert text == BaseGenerator(package_name=PKG, oas={}, copyright=text).copyright

    missing = "/no/such/copyright.txt"
    assert missing == BaseGenerator(package_name=PKG, oas={}, copyright=missing).copyright

    message = "# file copyright\n"
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "copyright.txt"
        path.write_text(message, encoding="utf-8")
        assert message == BaseGenerator(package_name=PKG, oas={}, copyright=path.as_posix()).copyright
        assert message == BaseGenerator(package_name=PKG, oas={}, copyright=path).copyright

        assert DEFAULT_COPYRIGHT == BaseGenerator(package_name=PKG, oas={}, copyright={"type": "error"}).copyright


def test_config():
    config = GeneratorConfig(
        package_name="cfg.name",
        max_help_length=3,
        default_host="https://192.168.1.1",
        default_log_level="error",
    )
    uut = BaseGenerator({}, package_name=PKG, config=config, default_log_level="debug")
    assert uut.package_name == PKG
    assert uut.max_help_length == 3
    assert uut.default_log == "debug"
    assert uut.default_host == "https://192.168.1.1"

    config = GeneratorConfig()
    with pytest.raises(ValueError, match="Missing package_name"):
        BaseGenerator({}, config=config)


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
    uut = BaseGenerator(oas={}, package_name=PKG)
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
    uut = BaseGenerator(oas={}, package_name=PKG)
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
    uut = BaseGenerator(oas={}, package_name=PKG)
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
        pytest.param("date", "--date", id="date"),
    ],
)
def test_option_name(proposed, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    assert expected == uut.option_name(proposed)


def test_shebang():
    uut = BaseGenerator(oas={}, package_name=PKG)
    text = uut.shebang()
    assert text.startswith("#!/")
    assert "python3" in text


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
    uut = BaseGenerator(oas={}, package_name=PKG)
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
def test_op_doc_string(op, expected):
    uut = BaseGenerator(package_name=PKG, oas={}, max_help_length=30)
    assert expected == uut.op_doc_string(op)


@pytest.mark.parametrize(
    ["path", "expected"],
    [
        pytest.param('foo', '_api_host, "foo"', id="foo"),
        pytest.param('foo/bar', '_api_host, "foo/bar"', id="foo/bar"),
        pytest.param('foo/{bar}', '_api_host, "foo", bar', id="foo/{bar}"),
        pytest.param('sna/foo/bar', '_api_host, "sna/foo/bar"', id="sna/foo/bar"),
        pytest.param('sna/{foo}/bar', '_api_host, "sna", foo, "bar"', id="sna/{foo}/bar"),
        pytest.param('sna/{foo}/{bar}', '_api_host, "sna", foo, bar', id="sna/{foo}/{bar}"),
    ]
)
def test_op_url_params(path, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    assert expected == uut.op_url_params(path)


def test_op_param_formation():
    oas = open_oas(asset_filename("misc3.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = BaseGenerator(oas=oas, package_name=PKG)
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
    oas = open_oas(asset_filename("misc3.yaml"))
    uut = BaseGenerator(oas=oas, package_name=PKG)

    assert expected == uut.schema_to_type(schema, fmt)


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        pytest.param(None, None, id="none"),
        pytest.param("foo", "foo", id="str"),
        pytest.param({"sna": "foo"}, {"sna": "foo"}, id="dict"),
        pytest.param(["sna", "foo"], "sna", id="list-no-null"),
        pytest.param(["null", "'null'"], None, id="list-multi-null"),
        pytest.param(["null", "sna"], "sna", id="list-null"),
        pytest.param(["null", "sna", "foo"], "sna", id="list-multi-value"),
        pytest.param(1, None, id="error"),
    ]
)
def test_simplify_type(schema, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    assert expected == uut.simplify_type(schema)

@pytest.mark.parametrize(
    ["param_data", "expected"],
    [
        pytest.param({}, None, id="unknown"),
        pytest.param({TYPE: "string"}, "str", id="str"),
        pytest.param({TYPE: "integer"}, "int", id="int"),
        pytest.param({TYPE: "numeric"}, "float", id="float"),
        pytest.param({TYPE: "string", ENUM: ["a", "b"], NAME: "sna_foo"}, "SnaFoo", id="unref-enum"),
        pytest.param(
            {TYPE: "string", ENUM: ["a", "b"], REFS: "#/comp/Schema/FooBar", NAME: "sna_foo"},
            "SnaFoo",
            id="ref-enum",
        ),
        pytest.param({TYPE: "object", PROPS: {TYPE: "string"}}, "dict[str, Any]", id="object"),
    ],
)
def test_get_parameter_pytype(param_data, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    assert expected == uut.get_parameter_pytype(param_data)


@pytest.mark.parametrize(
    ["prop_name", "prop_data", "expected"],
    [
        pytest.param("foo", {TYPE: "string", REQUIRED: True}, "str", id="str"),
        pytest.param("foo", {TYPE: "string", FORMAT: "date-time", REQUIRED: True}, "datetime", id="datetime"),
        pytest.param("foo", {TYPE: "string", FORMAT: "unknown", REQUIRED: False}, "str | None", id="optional-str"),
        pytest.param("foo", {TYPE: "integer"}, "int | None", id="optional-int"),
        pytest.param(
            "foo",
            {TYPE: "string", FORMAT: "date", COLLECT: "array", REQUIRED: True},
            "list[date]",
            id="list-date",
        ),
        pytest.param(
            "foo",
            {TYPE: "numeric", COLLECT: "array", REQUIRED: False},
            "list[float] | None",
            id="optional-list-float",
        ),
        pytest.param("foo", {TYPE: "foo"}, None, id="unknown"),
        pytest.param(
            "foo",
            {TYPE: "string", REQUIRED: True, ENUM: ["a", "b"], X_REF: "east_west"},
            "EastWest",
            id="named-enum",
        ),
        pytest.param(
            "foo",
            {TYPE: "string", REQUIRED: True, ENUM: ["a", "b"]},
            "Foo",
            id="unnamed-enum"
        ),
        pytest.param("foo", {TYPE: "object"}, None, id="object"),
        pytest.param(
            "foo",
            {TYPE: "object", ADDITIONAL_PROPS: {TYPE: "string"}},
            "str | None",
            id="add-props",
        ),
        pytest.param(
            "foo",
            {TYPE: "object", ADDITIONAL_PROPS: {TYPE: "string"}, REQUIRED: True},
            "str",
            id="add-props-req",
        ),
        pytest.param(
            "foo",
            {TYPE: "object", ADDITIONAL_PROPS: None},
            None,
            id="add-props-none"
        ),
        pytest.param(
            "foo",
            {TYPE: "object", ADDITIONAL_PROPS: True},
            None,
            id="add-props-bool"
        ),
        pytest.param(
            "foo",
            {TYPE: "object", ADDITIONAL_PROPS: {}},
            None,
            id="add-props-no-type"
        ),
    ],
)
def test_get_property_pytype(prop_name, prop_data, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    assert expected == uut.get_property_pytype(prop_name, prop_data)


@pytest.mark.parametrize(
    ["op_id", "expected"],
    [
        pytest.param("deleteSomething", '', id="None"),
        pytest.param("testPathParams", ', content_type="application/json"', id="JSON"),
    ],
)
def test_op_content_type(op_id, expected):
    oas = open_oas(asset_filename("misc3.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get(op_id)
    uut = BaseGenerator(oas=oas, package_name=PKG)

    assert expected == uut.op_content_header(op)


def test_op_body_formation_ref():
    oas = open_oas(asset_filename("misc3.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("testPathParams")
    uut = BaseGenerator(oas=oas, package_name=PKG)
    body_params = uut.op_body_settable_properties(op)
    text = uut.op_body_formation(body_params)
    assert "body = {}" in text
    assert 'body["id"]' not in text  # ignore read-only
    assert 'body["name"] = name' in text  # required
    assert 'if another_value is not None:' in text  # not required, so check if not None
    assert '_l.logger().warning("--another-value is deprecated and should not be used")' in text
    assert 'body["anotherValue"] = another_value' in text  # check prop vs variable name
    assert 'if bogus is not None:' not in text
    assert 'if flavor is not None:' in text
    assert 'body["flavor"] = flavor' in text
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


def test_op_body_formation_none():
    oas = open_oas(asset_filename("pet.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("showPetById")
    uut = BaseGenerator(oas=oas, package_name=PKG)
    body_params = uut.op_body_settable_properties(op)
    assert {} == body_params
    assert "" == uut.op_body_formation(body_params)


def test_op_body_formation_props() -> None:
    oas = open_oas(asset_filename("misc3.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("snaFooSearch")
    uut = BaseGenerator(oas=oas, package_name=PKG)
    body_params = uut.op_body_settable_properties(op)
    text = uut.op_body_formation(body_params)
    assert 'if situation is not None:' in text
    assert 'body["situation"] = situation' in text
    assert 'if deaths is not None:' in text
    assert 'body["deaths"] = deaths' in text


def test_op_body_formation_depth() -> None:
    oas = open_oas(asset_filename("misc3.yaml"))
    operations = map_operations(oas.get(OasField.PATHS))
    op = operations.get("createOwner")
    uut = BaseGenerator(oas=oas, package_name=PKG)
    body_params = uut.op_body_settable_properties(op)
    text = uut.op_body_formation(body_params)
    assert 'body = {}' in text
    assert 'home = {}' in text
    assert 'body["name"] = name' in text
    assert 'if ice_cream is not None:' in text
    assert 'body["iceCream"] = ice_cream' in text
    # test a couple of the home sub-object fields (no need to test all)
    assert 'if home_street is not None:' in text
    assert 'home["street"] = home_street' in text
    assert 'if home_city is not None:' in text
    assert 'home["city"] = home_city' in text
    # and, make sure the home sub-object is added to the main
    assert 'if home:' in text
    assert 'body["home"] = home' in text


@pytest.mark.parametrize(
    ["enum_type", "values", "expected"],
    [
        pytest.param('string', [1, "*"], True, id="str-match"),
        pytest.param('integer', [-1, 0, 1, 2, 3], True, id="int-match"),
        pytest.param('integer', [-1, 0.1, 1, 2, 3], False, id="int-diff"),
        pytest.param('numeric', [-1, 0, 1, 2, 3.14159], True, id="float-match"),
        pytest.param('numeric', [-1, 0.1, 1, 2, 3, '*'], False, id="float-diff"),
        pytest.param('boolean', [True, False, True, True], True, id='bool-match'),
        pytest.param('boolean', [False, 0, True], False, id="bool-diff"),
        pytest.param('foo', [1], False, id="unsupported"),
    ]
)
def test_enum_values_match_type(enum_type, values, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
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
    ENUM: ["aOrB", "b_or_C", "-minus"], REFS: "#/components/schemas/Simple",
    NAME: "simple",
}

NUMBER_PARAM = {TYPE: "integer", ENUM: [12, 37, 11], NAME: "simple-number"}
MIXED_PARAM = {TYPE: "string", ENUM: ["a", 1, True, "b"], NAME: "mixed-values"}
INT_STR_PARAM = {TYPE: "string", ENUM: ["10", "10.1"], NAME: "int-strings"}
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
    uut = BaseGenerator(oas={}, package_name=PKG)
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
            {"simple": {TYPE: "string", ENUM: ["aOrB", "b_or_C", "-minus"], X_REF: "Simple"}},
            f"\n{SIMPLE_ENUM}",
            id="ref-body",
        ),
        pytest.param(
            [SIMPLE_PARAM],
            [SIMPLE_PARAM],
            {"simple": {TYPE: "string", ENUM: ["aOrB", "b_or_C", "-minus"], X_REF: "Simple"}},
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
        ),
        pytest.param(
            [{NAME: "path_param"}],
            [{NAME: "qyery_param"}],
            {"body_param": {DEF: None}},
            "",
            id="no-values",
        )
    ],
)
def test_enum_definitions(path_params, query_params, body_params, expected):
    uut = BaseGenerator(oas={}, package_name=PKG)
    definitions = uut.enum_definitions(path_params, query_params, body_params)
    assert expected == definitions


@pytest.mark.parametrize(
    ["parameter", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param(SIMPLE_PARAM, SIMPLE_PROP, id="simple"),
        pytest.param(
            {ONE_OF: [{TYPE: "foo"}, {TYPE: "array", ITEMS: {TYPE: "foo"}}]},
            {TYPE: "foo", SINGLE: True},
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
            {TYPE: "sna", SINGLE: True},
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
    uut = BaseGenerator(oas={}, package_name=PKG)
    prop = uut.param_to_property(parameter)
    assert expected == prop


@pytest.mark.parametrize(
    ["model_name", "expected"],
    [
        pytest.param(
            "NoSuchModel",
            {},
            id="missing-model",
        ),
        pytest.param(
            "Owner",
            {
                'name': {
                    # NOTE: misspelling matches YAML
                    'descrption': 'Name of the pet owner',
                    TYPE: 'string',
                    REQUIRED: True,
                    X_REF: 'Person',
                    X_FIELD: 'name',
                },
                'home.street': {
                    DESC: 'Street address (e.g. 123 Main Street, POBox 507)',
                    TYPE: 'string',
                    REQUIRED: False,
                    X_REF: 'Address',
                    X_PARENTS: ['home'],
                    X_FIELD: 'street',
                },
                'home.city': {
                    TYPE: 'string',
                    REQUIRED: False,
                    X_REF: 'Address',
                    X_PARENTS: ['home'],
                    X_FIELD: 'city',
                },
                'home.state': {
                    TYPE: 'string',
                    REQUIRED: False,
                    X_REF: 'Address',
                    X_FIELD: 'state',
                    X_PARENTS: ['home'],
                },
                'home.zipCode': {
                    TYPE: 'string',
                    REQUIRED: False,
                    X_REF: 'Address',
                    X_FIELD: 'zipCode',
                    X_PARENTS: ['home'],
                },
                'iceCream': {
                    TYPE: 'string',
                    DESC: 'Favorite ice cream flavor',
                    REQUIRED: False,
                    X_REF: 'Owner',
                    X_FIELD: 'iceCream',
                }
            },
            id="Owner",
        ),
        pytest.param(
            "ObservationStationCollectionGeoJson",
            {
                # NOTE: features.id and features.type that come from GeoJsonFeatureCollection get overwritten.
                'features.properties.@id': {
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: '@id',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.@type': {
                    ENUM: ['wx:ObservationStation'],
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: '@type',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.county': {
                    DESC: 'A link to the NWS county zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'county',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.fireWeatherZone': {
                    DESC: 'A link to the NWS fire weather forecast zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'fireWeatherZone',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.forecast': {
                    DESC: 'A link to the NWS public forecast zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'forecast',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.geometry': {
                    DESC: 'A geometry represented in Well-Known Text (WKT) format.',
                    FORMAT: 'wkt',
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'geometry',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'GeometryString',
                },
                'features.properties.name': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.stationIdentifier': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'stationIdentifier',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.timeZone': {
                    FORMAT: 'iana-time-zone-identifier',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'timeZone',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'type': {
                    ENUM: ['FeatureCollection'],
                    TYPE: 'string',
                    REQUIRED: True,
                    X_REF: 'GeoJsonFeatureCollection',
                    X_FIELD: 'type',
                },
                'pagination.next':
                {
                    DESC: 'A link to the next page of records',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'next',
                    X_PARENTS: ['pagination'],
                    X_REF: 'PaginationInfo',
                },
                'observationStations': {
                    TYPE: 'string',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    COLLECT: 'array',
                    X_FIELD: 'observationStations',
                    X_REF: 'ObservationStationCollectionGeoJson',
                },
            },
            id="allOf-multi"
        ),
        pytest.param(
            "MultipleAnyOf",
            {
                'anotherValue': {
                    DEF: 'Anything goes',
                    DEPRECATED: True,
                    DESC: 'A string with a default',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'anotherValue',
                    X_REF: 'Pet',
                },
                'name': {
                    DESC: 'Pet name',
                    REQUIRED: True,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    X_REF: 'Pet',
                },
                'tag': {
                    DESC: 'Pet classification',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'tag',
                    X_REF: 'Pet',
                },
            },
            id="anyOf-multi",
        ),
        pytest.param(
            "GeoJsonFeatureCollection",
            {
                'type': {
                    ENUM: ['FeatureCollection'],
                    TYPE: 'string',
                    REQUIRED: True,
                    X_FIELD: 'type',
                    X_REF: 'GeoJsonFeatureCollection',
                },
                'features.id': {
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'id',
                    SINGLE: True,
                    X_PARENTS: ['features'],
                    X_REF: 'GeoJsonFeature',
                },
                'features.type': {
                    ENUM: ['Feature'],
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'type',
                    SINGLE: True,
                    X_PARENTS: ['features'],
                    X_REF: 'GeoJsonFeature',
                },
            },
            id="unnested",
        ),
        pytest.param(
            "DeeperNesting",
            {
                # NOTE: features.id and features.type that come from GeoJsonFeatureCollection get overwritten.
                'features.properties.@id': {
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: '@id',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.@type': {
                    ENUM: ['wx:ObservationStation'],
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: '@type',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.county': {
                    DESC: 'A link to the NWS county zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'county',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.fireWeatherZone': {
                    DESC: 'A link to the NWS fire weather forecast zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'fireWeatherZone',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.forecast': {
                    DESC: 'A link to the NWS public forecast zone containing this station.',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'forecast',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.geometry': {
                    DESC: 'A geometry represented in Well-Known Text (WKT) format.',
                    FORMAT: 'wkt',
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'geometry',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'GeometryString',
                },
                'features.properties.name': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.stationIdentifier': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'stationIdentifier',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'features.properties.timeZone': {
                    FORMAT: 'iana-time-zone-identifier',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'timeZone',
                    SINGLE: True,
                    X_PARENTS: ['features', 'properties'],
                    X_REF: 'ObservationStation',
                },
                'observationStations': {
                    TYPE: 'string',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    X_FIELD: 'observationStations',
                    X_REF: 'ObservationStationCollectionGeoJson',
                    COLLECT: 'array',
                },
                'owner.home.city': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'city',
                    X_PARENTS: ['owner', 'home'],
                    X_REF: 'Address',
                },
                'owner.home.state': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'state',
                    X_PARENTS: ['owner', 'home'],
                    X_REF: 'Address',
                },
                'owner.home.street': {
                    DESC: 'Street address (e.g. 123 Main Street, POBox 507)',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'street',
                    X_PARENTS: ['owner', 'home'],
                    X_REF: 'Address',
                },
                'owner.home.zipCode': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'zipCode',
                    X_PARENTS: ['owner', 'home'],
                    X_REF: 'Address',
                },
                'owner.iceCream': {
                    DESC: 'Favorite ice cream flavor',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'iceCream',
                    X_PARENTS: ['owner'],
                    X_REF: 'Owner',
                },
                'owner.name': {
                    # NOTE: misspelling matches YAML
                    'descrption': 'Name of the pet owner',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    X_PARENTS: ['owner'],
                    X_REF: 'Person',
                },
                'pagination.next': {
                    DESC: 'A link to the next page of records',
                    FORMAT: 'uri',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'next',
                    X_PARENTS: ['pagination'],
                    X_REF: 'PaginationInfo',
                },
                'type': {
                    ENUM: ['FeatureCollection'],
                    REQUIRED: True,
                    TYPE: 'string',
                    X_FIELD: 'type',
                    X_REF: 'GeoJsonFeatureCollection',
                },
            },
            id="nesting",
        ),
        pytest.param(
            "Attachment",
            {
                'bytes': {
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'bytes',
                },
                'date': {
                    FORMAT: 'date',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'date',
                },
                'edgeColor': {
                    ENUM: ['yellow', 'purple', 'blue'],
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Color',
                    X_FIELD: 'edgeColor',
                    X_ENUM: 'Color',
                },
                'id': {
                    'pattern': '^[0-9a-fA-F]{24}$',
                    TYPE: 'string',
                    REQUIRED: False,
                    X_REF: 'TrelloID',
                    X_FIELD: 'id',
                },
                'idMember': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'idMember',
                },
                'isUpload': {
                    REQUIRED: False,
                    TYPE: 'boolean',
                    X_REF: 'Attachment',
                    X_FIELD: 'isUpload',
                },
                'mimeType': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'mimeType',
                },
                'name': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'name',
                },
                'pos': {
                    FORMAT: 'float',
                    REQUIRED: False,
                    TYPE: 'number',
                    X_REF: 'Attachment',
                    X_FIELD: 'pos',
                },
                'previews': {
                    TYPE: 'string',
                    REQUIRED: False,
                    COLLECT: 'array',
                    X_REF: 'Attachment',
                    X_FIELD: 'previews',
                },
                'url': {
                    FORMAT: 'url',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'Attachment',
                    X_FIELD: 'url',
                }
            },
            id="item"
        ),
        pytest.param(
            "MultiAttachmentProperties",
            {
                'color': {
                    TYPE: 'string',
                    ENUM: ['yellow', 'purple', 'blue'],
                    REQUIRED: False,
                    NULLABLE: True,
                    X_FIELD: 'color',
                    X_REF: 'Color',
                    X_ENUM: 'Color',
                },
                'files.bytes': {
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'bytes',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.date': {
                    FORMAT: 'date',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'date',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.edgeColor': {
                    ENUM: ['yellow', 'purple', 'blue'],
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'edgeColor',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Color',
                    X_ENUM: 'Color',
                },
                'files.id': {
                    'pattern': '^[0-9a-fA-F]{24}$',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'id',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'TrelloID',
                },
                'files.idMember': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'idMember',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.isUpload': {
                    REQUIRED: False,
                    TYPE: 'boolean',
                    X_FIELD: 'isUpload',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
               'files.mimeType': {
                   REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'mimeType',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.name': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.pos': {
                    FORMAT: 'float',
                    REQUIRED: False,
                    TYPE: 'number',
                    X_FIELD: 'pos',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.previews': {
                    REQUIRED: False,
                    TYPE: 'string',
                    COLLECT: 'array',
                    X_FIELD: 'previews',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
                'files.url': {
                    FORMAT: 'url',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'url',
                    SINGLE: True,
                    X_PARENTS: ['files'],
                    X_REF: 'Attachment',
                },
            },
            id="list-all-of"
        ),
        pytest.param(
            "MultiAttachmentList",
            {
                'bytes': {
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'bytes',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'date': {
                    FORMAT: 'date',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'date',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'edgeColor': {
                    ENUM: ['yellow', 'purple', 'blue'],
                    NULLABLE: True,
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'edgeColor',
                    SINGLE: True,
                    X_REF: 'Color',
                    X_ENUM: 'Color',
                },
                'id': {
                    'pattern': '^[0-9a-fA-F]{24}$',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'id',
                    SINGLE: True,
                    X_REF: 'TrelloID',
                },
                'idMember': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'idMember',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'isUpload': {
                    REQUIRED: False,
                    TYPE: 'boolean',
                    X_FIELD: 'isUpload',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'mimeType': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'mimeType',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'name': {
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'name',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'pos': {
                    FORMAT: 'float',
                    REQUIRED: False,
                    TYPE: 'number',
                    X_FIELD: 'pos',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'previews': {
                    REQUIRED: False,
                    TYPE: 'string',
                    COLLECT: 'array',
                    X_FIELD: 'previews',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
                'url': {
                    FORMAT: 'url',
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'url',
                    SINGLE: True,
                    X_REF: 'Attachment',
                },
            },
            id="list-ref",
        ),
        pytest.param(
            "EnumListProperty",
            {
                'rainbow': {
                    TYPE: 'string',
                    ENUM: ['yellow', 'purple', 'blue'],
                    REQUIRED: True,
                    NULLABLE: True,
                    X_REF: 'Color',
                    COLLECT: 'array',
                    X_FIELD: 'rainbow',
                    X_ENUM: 'Color',
                }
            },
            id="list-enum",
        ),
        pytest.param(
            "MissingInheritedSubmodel",
            {'sna': {TYPE: 'string', REQUIRED: True, X_FIELD: 'sna', X_REF: 'MissingInheritedSubmodel'}},
            id="missing-submodel",
        ),
        pytest.param(
            "MissingSubmodelProperty",
            {'bar': {TYPE: 'string', REQUIRED: False, X_FIELD: 'bar', X_REF: 'MissingSubmodelProperty'}},
            id="missing-submodel",
        ),
        pytest.param(
            "MissingItemsModel",
            {'foo': {TYPE: 'integer', REQUIRED: False, X_FIELD: 'foo', X_REF: 'MissingItemsModel'}},
            id="missing-items",
        ),
        pytest.param(
            "MembershipCreate",
            {
                'role': {
                    ENUM: ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    REQUIRED: True,
                    TYPE: 'string',
                    X_REF: 'RoleEnum',
                    DESC: 'The role that the user has in the organization.',
                    X_FIELD: 'role',
                    X_ENUM: 'RoleEnum',
                },
                'user': {
                    DESC: 'The user of the membership.',
                    FORMAT: 'uri',
                    REQUIRED: True,
                    TYPE: 'string',
                    X_FIELD: 'user',
                    X_REF: 'MembershipCreate',
                },
            },
            id="enum-all-of"
        ),
        pytest.param(
            "MembershipCreateAnyOf",
            {
                'role': {
                    DESC: 'The role that the user has in the organization.',
                    ENUM: ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    REQUIRED: False,
                    TYPE: 'string',
                    X_FIELD: 'role',
                    X_REF: 'RoleEnum',
                    X_ENUM: 'RoleEnum',
                },
            },
            id="enum-any-of"
        ),
        pytest.param(
            "MembershipCreateOneOf",
            {
                'role': {
                    ENUM: ['OWNER', 'ADMIN', 'CONTRIB', 'VIEWER'],
                    REQUIRED: False,
                    TYPE: 'string',
                    X_REF: 'RoleEnum',
                    X_FIELD: 'role',
                    X_ENUM: 'RoleEnum',
                    DESC: 'The role that the user has in the organization.',
                },
            },
            id="enum-one-of"
        ),
    ]
)
def test_model_settable_properties(model_name, expected):
    oas = open_oas(asset_filename("misc3.yaml"))
    uut = BaseGenerator(oas=oas, package_name=PKG)
    model = uut.get_model(f"#/components/schemas/{model_name}")
    properties = uut.model_settable_properties(model_name, model)
    assert expected == properties


def test_add_init_file() -> None:
    uut = BaseGenerator(oas={}, package_name=PKG)

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "__init__.py"
        assert not path.exists()

        uut.add_init_file(temp_dir)
        assert path.exists()
        assert "" == path.read_text()

        text = "sna\r\nfoo\r\nbar\r\n"

        # do not overwrite unless told to do so
        uut.add_init_file(temp_dir, text)
        assert "" == path.read_text()

        uut.add_init_file(temp_dir, text, True)
        expected = text.replace("\r\n", "\n")  # replace line endings
        assert expected == path.read_text()


def test_copy_infrastructure() -> None:
    uut = BaseGenerator(oas={}, package_name=PKG)

    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)

        # nothing present for copy/replace
        uut.copy_infrastructure_files(temp_dir)
        files = {_.name for _ in directory.iterdir()}
        assert not files

        # copy and replace "random" file
        dname = "foo.yaml"
        title = "My Favorite Petstore"
        uut.infra_files = {Path(asset_filename("pet.yaml")) : dname}
        uut.infra_replacements = {"Swagger Petstore": title}

        uut.copy_infrastructure_files(temp_dir)
        files = {_.name for _ in directory.iterdir()}
        assert files == {dname}
        content = (directory / dname).read_text()
        assert title in content


def test_copy_tests() -> None:
    uut = BaseGenerator(oas={}, package_name=PKG)

    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)

        # nothing present for copy/replace
        uut.copy_test_files(temp_dir)
        files = {_.name for _ in directory.iterdir()}
        assert not files

        # copy and replace "random" file
        dname = "bar.yaml"
        url = "http://localhost/v1"
        uut.test_files = {Path(asset_filename("pet.yaml")) : dname}
        uut.test_replacements = {" http://petstore.swagger.io/v1": url}

        uut.copy_test_files(temp_dir)
        files = {_.name for _ in directory.iterdir()}
        assert files == {dname}
        content = (directory / dname).read_text()
        assert url in content
