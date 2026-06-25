import pytest

from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
from openapi_spec_tools.layout.utils import check_hardcoded
from openapi_spec_tools.layout.utils import check_pagination_definitions
from openapi_spec_tools.layout.utils import data_to_node
from openapi_spec_tools.layout.utils import field_to_list
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.layout.utils import layout_node_to_dict
from openapi_spec_tools.layout.utils import open_layout
from openapi_spec_tools.layout.utils import operation_duplicates
from openapi_spec_tools.layout.utils import operation_order
from openapi_spec_tools.layout.utils import pagination_to_dict
from openapi_spec_tools.layout.utils import parse_extras
from openapi_spec_tools.layout.utils import parse_hardcoded
from openapi_spec_tools.layout.utils import parse_pagination
from openapi_spec_tools.layout.utils import parse_to_tree
from openapi_spec_tools.layout.utils import path_to_parts
from openapi_spec_tools.layout.utils import subcommand_missing_properties
from openapi_spec_tools.layout.utils import subcommand_order
from openapi_spec_tools.layout.utils import subcommand_references
from tests.helpers import asset_filename

OPS = "operations"
DESC = "description"
NAME = "name"
OP_ID = "operationId"
PAGE = "pagination"
SUB_ID = "subcommandId"
REF = "reference"
ONE_OF_MSG = f"{OP_ID}, {SUB_ID}, or {REF}"
HARD = "hardCoded"
VALUE = "value"


def test_open_layout() -> None:
    data = open_layout(asset_filename("layout_pets.yaml"))
    assert data is not None

    with pytest.raises(FileNotFoundError):
        open_layout("no-such-file")


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param({"cmd": {}}, {"cmd": f"{DESC}, {OPS}"}, id="all"),
        pytest.param({"cmd": {DESC: "foo"}}, {"cmd": OPS}, id="operations"),
        pytest.param({"cmd": {OPS: []}}, {"cmd": DESC}, id="description"),
        pytest.param(
            {"cmd": {DESC: "foo", OPS: [{NAME: "sub1"}]}},
            {"cmd": f"sub1 {ONE_OF_MSG}"},
            id="op-sub-or-id",
        ),
        pytest.param(
            {"cmd": {DESC: "foo", OPS: [{OP_ID: "bar"}]}},
            {"cmd": "operation[0] name"},
            id="op-name",
        ),
        pytest.param(
            {"cmd": {DESC: "foo", OPS: [{}]}},
            {"cmd": f"operation[0] name, operation[0] {ONE_OF_MSG}"},
            id="op-all",
        ),
        pytest.param(
            {
                "cmd": {DESC: "sna"},
                "prov": {DESC: "foo", OPS: [{NAME: "bar"}]},
                "resp": {DESC: "short", OPS: [{NAME: "blah", OP_ID: "op1"}]},
            },
            {"cmd": OPS, "prov": f"bar {ONE_OF_MSG}"},
            id="many",
        )
    ]
)
def test_missing_properties(data, expected) -> None:
    assert expected == subcommand_missing_properties(data)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param(
            {"cmd": {OPS: [{NAME: "foo"}, {NAME: "foo"}]}},
            {"cmd": "foo at 0, 1"},
            id="simple",
        ),
        pytest.param(
            {"cmd": {OPS: [
                {NAME: "sna"},
                {NAME: "foo"},
                {NAME: "bar"},
                {NAME: "bar"},
                {NAME: "sna"},
            ]}},
            {"cmd": "bar at 2, 3; sna at 0, 4"},
            id="multiple-one-command",
        ),
        pytest.param(
            {"cmd": {OPS: [
                    {NAME: "sna"},
                    {NAME: "foo"},
                    {NAME: "bar"},
                    {NAME: "bar"},
                    {NAME: "sna"},
            ]}},
            {"cmd": "bar at 2, 3; sna at 0, 4"},
            id="multiple-commands",
        ),
        pytest.param(
            {"cmd": {OPS: [{OP_ID: "op1"}, {NAME: "sna"}, {OP_ID: "op2"}, {NAME: "sna"}]}},
            {"cmd": "sna at 1, 3"},
            id="unnamed",
        )
    ]
)
def test_shadow_operations(data, expected) -> None:
    assert expected == operation_duplicates(data)


@pytest.mark.parametrize(
    ["data", "expected_unused", "expected_missing"],
    [
        pytest.param({}, set(), set(), id="empty"),
        pytest.param(
            {"main": {OPS: [{SUB_ID: "sub1"}, {SUB_ID: "sub2"}]}, "sub2": {}},
            set(),
            {"sub1"},
            id="missing",
        ),
        pytest.param(
            {"main": {OPS: [{SUB_ID: "sub1"}]}, "sub1": {}, "sub2": {} },
            {"sub2"},
            set(),
            id="unused",
        ),
        pytest.param(
            {"main": {OPS: [{SUB_ID: "sub1"}, {SUB_ID: "sub2"}]}, "sub2": {}, "sub3": {}},
            {"sub3"},
            {"sub1"},
            id="both",
        ),
        pytest.param(
            {
                "main": {
                    OPS: [{SUB_ID: "sub1"}, {SUB_ID: "sub2"}, {SUB_ID: "sub4"}, {SUB_ID: "sub5"}]
                },
                "sub2": {},
                "sub3": {},
                "sub4": {},
                "sub6": {},
            },
            {"sub3", "sub6"},
            {"sub1", "sub5"},
            id="multiples",
        ),
    ]
)
def test_subcommand_references(data, expected_unused, expected_missing):
    unused, missing = subcommand_references(data)
    assert (unused, missing) == (expected_unused, expected_missing)


@pytest.mark.parametrize(
    ["data", "field", "expected"],
    [
        pytest.param({}, "foo", [], id="empty"),
        pytest.param({"a": None}, "a", [], id="no-body"),
        pytest.param({"a": []}, "a", [], id="empty-list"),
        pytest.param({"a": [""]}, "a", [], id="list-empty-str"),
        pytest.param({"a": ["2 2", "1 "]}, "a", ["2 2", "1"], id="list-stripped"),
        pytest.param({"a": ""}, "a", [], id="empty-str"),
        pytest.param({"a": "b"}, "a", ["b"], id="str-simple"),
        pytest.param({"a": "c d,  b , "}, "a", ["c d", "b"], id="str-stripped"),
    ]
)
def test_field_list(data, field, expected) -> None:
    assert expected == field_to_list(data, field)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param({OP_ID: "op1", SUB_ID: "sub1", DESC: "desc"}, {}, id="remove-fields"),
        pytest.param({"sna": "foo", OP_ID: "op1", "foo": "bar"}, {"sna": "foo", "foo": "bar"}, id="pass"),
        pytest.param({"sna": {"foo": "bar"}, OP_ID: "a"}, {"sna": {"foo": "bar"}}, id="complex"),
    ]
)
def test_parse_extras(data, expected) -> None:
    assert expected == parse_extras(data)


@pytest.mark.parametrize(
    ["path", "prefix", "expected"],
    [
        pytest.param("", "", [], id="empty"),
        pytest.param("/foo", "/foo", [], id="only-prefix"),
        pytest.param("/foo", "/foo/foo", ["foo"], id="single-prefix"),
        pytest.param("/foo/{bar}", "/foo", [], id="prefix-id"),
        pytest.param("/sna/foo/{bar}", "/foo", ["sna", "foo"], id="late-prefix"),
        pytest.param("/sna/foo/{bar}/all", "/sna", ["foo", "all"], id="all"),
    ],
)
def test_path_to_parts(path, prefix, expected):
    assert expected == path_to_parts(path, prefix)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param(None, None, id="none"),
        pytest.param({}, None, id="empty"),
        pytest.param({"foo": "bar"}, PaginationNames(), id="no-props"),
        pytest.param(
            {
                "itemProperty": "north",
                "itemStart": "south",
                "nextHeader": "east",
                "nextProperty": "west",
                "pageSize": "up",
                "pageStart": "down",
            },
            PaginationNames(
                page_size="up",
                page_start="down",
                item_start="south",
                items_property="north",
                next_header="east",
                next_property="west",
            ),
            id="all",
        )
    ]
)
def test_parse_pagination(data, expected) -> None:
    assert expected == parse_pagination(data)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param(None, {}, id="none"),
        pytest.param("not a list", {}, id="str"),
        pytest.param({"A": None}, {}, id="dict"),
        pytest.param([], {}, id="empty"),
        pytest.param([{"name": "a", "value": 1}], {"a": 1}, id="simple"),
        pytest.param([{"name": "a", "value": 1}, {"name": "b", "value": True}], {"a": 1, "b": True}, id="multiple"),
        pytest.param(
            [{"value": 1}, {"name": "b"}, {"name": "c", "value": "mystr"}, {"d": 0}],
            {"c": "mystr"},
            id="bad-entries",
        ),
    ]
)
def test_parse_hardcoded(data, expected) -> None:
    assert expected == parse_hardcoded(data)


@pytest.mark.parametrize(
    ["name", "expected"],
    [
        pytest.param("update", {}, id="none"),
        pytest.param("create", {"name": "toulouse"}, id="simple"),
        pytest.param("delete", {"sna": "foo"}, id="errors"),
        pytest.param("examine", {}, id="bad"),
    ]
)
def test_parse_with_hardcoded(name, expected) -> None:
    node = file_to_tree(asset_filename("layout_hardcoded.yaml"))

    item = node.find("pet", name)
    assert expected == item.hardcoded


@pytest.mark.parametrize(
    [NAME, "item", "expected"],
    [
        pytest.param(
            "sna",
            {},
            LayoutNode(
                command="sna",
                identifier="sna",
            ),
            id="empty",
        ),
        pytest.param(
            "sna",
            {
                DESC: "my desc",
                "bugIds": "a, b",
                "summaryFields": ["foo", "bar"],
                "hiddenFields": ["east", "west"],
                "allowedFields": ["patriots", "celtics"],
                "my-party": {"cry": "if i want to"},
                "columns": "a, b, c",
                OP_ID: "op1",
                OPS: [],
            },
            LayoutNode(
                command="sna",
                identifier="sna",
                description="my desc",
                bugs=["a", "b"],
                summary_fields=["foo", "bar"],
                extra={"my-party": {"cry": "if i want to"}},
                children=[],
                hidden_fields=["east", "west"],
                allowed_fields=["patriots", "celtics"],
                display_columns=["a", "b", "c"],
            ),
            id="fields",
        ),
        pytest.param(
            "sna",
            {
                OPS: [
                    {NAME: "foo", OP_ID: "op1"}, {NAME: "bar", OP_ID: "op2"}
                ],
            },
            LayoutNode(
                command="sna",
                identifier="sna",
                children=[
                    LayoutNode(command="foo", description="", identifier="op1"),
                    LayoutNode(command="bar", description="", identifier="op2"),
                ],
            ),
            id="sub-ops",
        ),
        pytest.param(
            "sna",
            {
                OPS: [
                    {NAME: "foo", SUB_ID: "sub1"}, {NAME: "bar", SUB_ID: "sub2"}
                ],
            },
            LayoutNode(
                command="sna",
                identifier="sna",
                children=[
                    LayoutNode(command="foo", identifier="sub1", description="sub-command desc", children=[
                        LayoutNode(command="dazed", identifier="confused"),
                    ]),
                    LayoutNode(command="bar", identifier="sub2", description="more help", bugs=["a", "bc"]),
                ],
            ),
            id="sub-cmds",
        ),
        pytest.param(
            "sna",
            {
                OPS: [
                    {NAME: "foo", SUB_ID: "sub1"}, {NAME: "bar", SUB_ID: "sub2", "bugIds": "x, y"}
                ],
            },
            LayoutNode(
                command="sna",
                identifier="sna",
                children=[
                    LayoutNode(command="foo", identifier="sub1", description="sub-command desc", children=[
                        LayoutNode(command="dazed", identifier="confused"),
                    ]),
                    LayoutNode(command="bar", identifier="sub2", description="more help", bugs=["a", "bc", "x", "y"]),
                ],
            ),
            id="sub-cmd-bug",
        ),
    ],
)
def test_data_to_node_basic(name, item, expected) -> None:
    data = {
        "sub1": {
            DESC: "sub-command desc",
            OPS: [{NAME: "dazed", OP_ID: "confused"}]
        },
        "sub2": {
            DESC: "more help",
            "bugIds": "a, bc",
        }
    }
    node = data_to_node(data, name, name, item)
    assert expected == node


@pytest.mark.parametrize(
    ["start", "expected"],
    [
        pytest.param(
            "top",
            LayoutNode(
                command="top",
                identifier="top",
                description="top level item",
                children=[
                    LayoutNode(
                        command="blah",
                        identifier="command1",
                        children=[
                            LayoutNode(command="foo", identifier="op1"),
                            LayoutNode(command="bar", identifier="op2"),
                        ],
                    ),
                    LayoutNode(
                        command="zey",
                        identifier="command2",
                        description="some help"
                    )
                ]
            ),
            id="top",
        ),
        pytest.param(
            "command2",
            LayoutNode(command="command2", identifier="command2", description="some help"),
            id="command2",
        ),
        pytest.param(
            "command1",
            LayoutNode(
                command="command1",
                identifier="command1",
                children=[
                    LayoutNode(command="foo", identifier="op1"),
                    LayoutNode(command="bar", identifier="op2"),
                ],
            ),
            id="command1",
        )
    ]
)
def test_parse_to_tree_success(start, expected) -> None:
    data = {
        "top": {
            DESC: "top level item",
            OPS: [{NAME: "blah", SUB_ID: "command1"}, {NAME: "zey", SUB_ID: "command2"}]
        },
        "command1": {
            OPS: [{NAME: "foo", OP_ID: "op1"}, {NAME: "bar", OP_ID: "op2"}]
        },
        "command2": {
            DESC: "some help"
        }
    }
    node = parse_to_tree(data, start)
    assert expected == node


def test_parse_to_tree_error() -> None:
    data = {"sna": "foo"}
    with pytest.raises(ValueError, match="No start value found for "):
        parse_to_tree(data, "foo")


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param({}, {}, id="empty"),
        pytest.param({"a": None}, {}, id="no-body"),
        pytest.param({"a": {OPS: [{NAME: "C"}, {NAME: "M"}, {NAME: "P"}]}}, {}, id="ordered"),
        pytest.param({"a": {OPS: [{NAME: "A"}, {NAME: "Z"}, {NAME: "F"}]}}, {"a": "A, F, Z"}, id="misordered")
    ]
)
def test_operations_order(data, expected) -> None:
    assert expected == operation_order(data)


@pytest.mark.parametrize(
    ["data", "start", "expected"],
    [
        pytest.param({}, "foo", [], id="empty"),
        pytest.param({"a": {}}, "b", ["First should be b"], id="first"),
        pytest.param({"a": {}, "d": {}, "c": {}}, "a", ["c < d"], id="simple"),
        pytest.param({"a": {}, "d": {}, "c": {}}, "d", ["First should be d", "c < d"], id="first-plus"),
        pytest.param(
            {"a": {}, "c": {}, "b": {}, "m": {}, "n": {}, "o": {}, "l": {}},
            "a",
            ["b < c", "l < o"],
            id="multiple",
        )
    ]
)
def test_subcommand_order(data, start, expected) -> None:
    assert expected == subcommand_order(data, start)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param(
            {"a": {OPS: [{NAME: "foo"}]}},
            {},
            id="no-page",
        ),
        pytest.param(
            {"a": {OPS: [{NAME: "foo", PAGE: {"bar": 1}}]}},
            {"a.foo": "unsupported parameters: bar"},
            id="unsuppoted",
        ),
        pytest.param(
            {"a": {OPS: [{NAME: "foobar", PAGE: {"nextHeader": "Location", "nextProperty": "nextUrl"}}]}},
            {"a.foobar": "cannot have next URL in both header and body property"},
            id="next",
        ),
        pytest.param(
            {"b": {OPS: [{NAME: "snafoo", PAGE: {"itemStart": "offset", "pageStart": "page"}}]}},
            {"b.snafoo": "start can only be specified with page or item paramter"},
            id="page",
        ),
    ]
)
def test_pagination_definitions(data, expected) -> None:
    assert expected == check_pagination_definitions(data)


@pytest.mark.parametrize(
    ["data", "expected"],
    [
        pytest.param(
            {"a": {OPS: [{NAME: "foo"}]}},
            {},
            id="no-hard",
        ),
        pytest.param(
            {"b": {OPS: [{NAME: "foo", HARD: [{NAME: "sna", VALUE: "bar"}]}]}},
            {},
            id="simple",
        ),
        pytest.param(
            {"c": {OPS: [{NAME: "foo", HARD: {NAME: "sna", VALUE: "bar"}}]}},
            {"c.foo": "must be a list of parameter name/values"},
            id="non-list",
        ),
        pytest.param(
            {"d": {OPS: [{NAME: "foo", HARD: ["sna: bar"]}]}},
            {"d.foo": "index#0 must be a dictionary"},
            id="non-dict",
        ),
        pytest.param(
            {"e": {OPS: [{NAME: "foo", HARD: [{NAME: "sna"}, {VALUE: 1}]}]}},
            {"e.foo": "index#0 missing value; index#1 missing name"},
            id="missing",
        ),
        pytest.param(
            {"f": {OPS: [{NAME: "foo", HARD: [{NAME: "sna", VALUE: "foo", "a": 1}]}]}},
            {"f.foo": "index#0 unsupported parameters: a"},
            id="unsupported",
        ),
    ],
)
def test_check_hardcoded(data, expected) -> None:
    assert expected == check_hardcoded(data)


def test_lists() -> None:
    uut = LayoutNode(
        command="top",
        identifier="top",
        description="top level item",
        children=[
            LayoutNode(
                command="blah",
                identifier="command1",
                children=[
                    LayoutNode(command="foo", identifier="op1"),
                    LayoutNode(command="bar", identifier="op2"),
                ],
            ),
            LayoutNode(
                command="zey",
                identifier="command2",
                description="some help",
            )
        ]
    )
    subcommands = uut.subcommands()
    assert 1 == len(subcommands)
    assert "blah" == subcommands[0].command
    operations = uut.operations()
    assert 1 == len(operations)
    assert "zey" == operations[0].command


def test_lists_bugged() -> None:
    uut = LayoutNode(
        command="top",
        identifier="top",
        description="top level item",
        children=[
            LayoutNode(
                command="blah",
                identifier="command1",
                bugs=["456"],
                children=[
                    LayoutNode(command="foo", identifier="op1"),
                    LayoutNode(command="bar", identifier="op2", bugs=["abc"]),
                ],
            ),
            LayoutNode(
                command="zey",
                identifier="command2",
                description="some help",
                bugs=["123"],
            )
        ]
    )

    # test defaults -- ignore bugged
    subcommands = uut.subcommands()
    assert 0 == len(subcommands)
    operations = uut.operations()
    assert 0 == len(operations)

    # test including bugged items
    subcommands = uut.subcommands(include_all=True)
    assert 1 == len(subcommands)
    operations = uut.operations(include_all=True)
    assert 1 == len(operations)


def test_file_to_tree() -> None:
    filename = asset_filename("layout_pets2.yaml")
    tree = file_to_tree(filename)
    assert "main" == tree.command
    assert set({"owners", "pet", "vets"}) == {p.command for p in tree.subcommands()}

    tree = file_to_tree(filename, "owners")
    assert "owners" == tree.command
    assert set() == {p.command for p in tree.subcommands()}


ALL_PAGE_DICT = {
    "itemProperty": "itemProp",
    "itemStart": "item",
    "pageStart": "page",
    "pageSize": "size",
    "nextHeader": "My-header",
    "nextProperty": "nextProp",
}
ITEMS_PAGE_DICT = {
    "itemProperty": "itemProp",
    "itemStart": "item",
}

@pytest.mark.parametrize(
    ["pagination", "expected"],
    [
        pytest.param(
            PaginationNames(
                page_size="size",
                page_start="page",
                item_start="item",
                items_property="itemProp",
                next_property="nextProp",
                next_header="My-header",
            ),
            ALL_PAGE_DICT,
            id="all",
        ),
        pytest.param(
            PaginationNames(item_start="item", items_property="itemProp"),
            ITEMS_PAGE_DICT,
            id="items",
        ),
    ]
)
def test_pagination_to_dict(pagination, expected):
    actual = pagination_to_dict(pagination)
    assert expected == actual


def test_layout_node_to_dict():
    node = LayoutNode(
        command="parent",
        identifier="this_is_it",
        description="summary",
        children=[
            LayoutNode(
                command="child3",
                identifier="more_ops",
                bugs=["mosquito", "spider"],
                hidden_fields=["peekaboo"],
                summary_fields=["brief", "short"],
                allowed_fields=["a", "b", "c"],
                display_columns=["west", "east"]
            ),
            LayoutNode(command="child1", identifier="my_child", pagination=PaginationNames(page_size="page")),
            LayoutNode(command="child2", identifier="another_op", ignore=True),
            LayoutNode(command="child4", identifier="with_hardcoded", hardcoded={"c": True, "x": "y", "a": 1}),
        ]
    )
    actual = layout_node_to_dict(node)
    assert actual == {
        "this_is_it": {
            "description": "summary",
            "operations": [
                {
                    "name": "child1",
                    "operationId": "my_child",
                    "pagination": {"pageSize": "page"},
                },
                {
                    "name": "child2",
                    "operationId": "another_op",
                    "ignore": True,
                },
                {
                    "name": "child3",
                    "operationId": "more_ops",
                    "bugIds": ["mosquito", "spider"],
                    "allowedFields": ["a", "b", "c"],
                    "hiddenFields": ["peekaboo"],
                    "summaryFields": ["brief", "short"],
                    "columns": ["west", "east"],
                },
                {
                    "hardCoded": {"a": 1, "c": True, "x": "y"},
                    "name": "child4",
                    "operationId": "with_hardcoded",
                },
            ]
        }
    }
