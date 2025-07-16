import pytest

from openapi_spec_tools.cli_gen.layout import check_pagination_definitions
from openapi_spec_tools.cli_gen.layout import data_to_node
from openapi_spec_tools.cli_gen.layout import field_to_list
from openapi_spec_tools.cli_gen.layout import file_to_tree
from openapi_spec_tools.cli_gen.layout import open_layout
from openapi_spec_tools.cli_gen.layout import operation_duplicates
from openapi_spec_tools.cli_gen.layout import operation_order
from openapi_spec_tools.cli_gen.layout import parse_extras
from openapi_spec_tools.cli_gen.layout import parse_pagination
from openapi_spec_tools.cli_gen.layout import parse_to_tree
from openapi_spec_tools.cli_gen.layout import subcommand_missing_properties
from openapi_spec_tools.cli_gen.layout import subcommand_order
from openapi_spec_tools.cli_gen.layout import subcommand_references
from openapi_spec_tools.cli_gen.layout_types import LayoutNode
from openapi_spec_tools.cli_gen.layout_types import PaginationNames
from tests.helpers import asset_filename

OPS = "operations"
DESC = "description"
NAME = "name"
OP_ID = "operationId"
PAGE = "pagination"
SUB_ID = "subcommandId"


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
            {"cmd": f"sub1 {OP_ID} or {SUB_ID}"},
            id="op-sub-or-id",
        ),
        pytest.param(
            {"cmd": {DESC: "foo", OPS: [{OP_ID: "bar"}]}},
            {"cmd": "operation[0] name"},
            id="op-name",
        ),
        pytest.param(
            {"cmd": {DESC: "foo", OPS: [{}]}},
            {"cmd": f"operation[0] name, operation[0] {OP_ID} or {SUB_ID}"},
            id="op-all",
        ),
        pytest.param(
            {
                "cmd": {DESC: "sna"},
                "prov": {DESC: "foo", OPS: [{NAME: "bar"}]},
                "resp": {DESC: "short", OPS: [{NAME: "blah", OP_ID: "op1"}]},
            },
            {"cmd": OPS, "prov": f"bar {OP_ID} or {SUB_ID}"},
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
                "my-party": {"cry": "if i want to"},
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
    subcommands = uut.subcommands(include_bugged=True)
    assert 1 == len(subcommands)
    operations = uut.operations(include_bugged=True)
    assert 1 == len(operations)


def test_file_to_tree() -> None:
    filename = asset_filename("layout_pets2.yaml")
    tree = file_to_tree(filename)
    assert "main" == tree.command
    assert set({"owners", "pet", "vets"}) == {p.command for p in tree.subcommands()}

    tree = file_to_tree(filename, "owners")
    assert "owners" == tree.command
    assert set() == {p.command for p in tree.subcommands()}


@pytest.mark.parametrize(
    ["search_args", "expected"],
    [
        pytest.param(("foo"), None, id="not-found"),
        pytest.param(("pet", "feed"), None, id="child-not-found"),
        pytest.param(
            ("pet", "create"),
            LayoutNode(command="create", identifier="createPets", summary_fields=["name"]),
            id="child",
        ),
    ]
)
def test_node_find(search_args, expected) -> None:
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    assert expected == tree.find(*search_args)
