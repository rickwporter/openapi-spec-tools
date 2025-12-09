import pytest

from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
from openapi_spec_tools.layout.types import ReferenceSubcommand
from openapi_spec_tools.layout.utils import file_to_tree
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["node", "sparse", "expected"],
    [
        pytest.param(
            LayoutNode("sna", "foo"),
            True,
            {"command": "sna", "identifier": "foo", "description": ""},
            id="basic",
        ),
        # TODO: test with non-sparse (not working)
    ]
)
def test_node_dict(node, sparse, expected):
    assert expected == node.as_dict(sparse)


@pytest.mark.parametrize(
    ["search_args", "expected"],
    [
        pytest.param((), None, id="no-args"),
        pytest.param(("foo"), None, id="not-found"),
        pytest.param(("pet", "feed"), None, id="child-not-found"),
        pytest.param(
            ("pet", "create"),
            LayoutNode(
                command="create",
                identifier="createPets",
                summary_fields=["name"],
                hidden_fields=["sna", "foo", "bar"],
                allowed_fields=["red-sox", "bruins"],
                display_columns=["east", "south", "north"],
            ),
            id="child",
        ),
    ]
)
def test_node_find(search_args, expected) -> None:
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    assert expected == tree.find(*search_args)


@pytest.mark.parametrize(
    ["node", "num_ops_all", "num_ops_live", "num_sub_all", "num_sub_live"],
    [
        pytest.param(
            LayoutNode(command="foo", identifier="bar"), 0, 0, 0, 0, id="none"
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo"),
                    LayoutNode("sna", "foo", children=[LayoutNode("a", "b")])
                ]
            ),
            1,
            1,
            1,
            1,
            id="no-skip",
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo"),
                    LayoutNode("sna", "foo", ignore=True),
                    LayoutNode("sna", "foo", bugs=["a"]),
                ]
            ),
            3,
            1,
            0,
            0,
            id="ops",
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo", children=[LayoutNode("a", "b")]),
                    LayoutNode("sna", "foo", ignore=True, children=[LayoutNode("a", "b")]),
                    LayoutNode("sna", "foo", bugs=["a"], children=[LayoutNode("a", "b")]),
                ]
            ),
            0,
            0,
            3,
            1,
            id="subs",
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode(
                        "sna",
                        "foo",
                        children=[LayoutNode("a", "b"), LayoutNode("c", "d", ignore=True)]
                    ),
                    LayoutNode(
                        "sna",
                        "foo",
                        children=[LayoutNode("w", "x", ignore=True), LayoutNode("y", "z", bugs=["1"])],
                    )
                ]
            ),
            0,
            0,
            2,
            1,
            id="subs-children",
        )
    ]
)
def test_node_children(node: LayoutNode, num_ops_all, num_ops_live, num_sub_all, num_sub_live):
    assert num_ops_all == len(node.operations(include_all=True))
    assert num_ops_live == len(node.operations())

    assert num_sub_all == len(node.subcommands(include_all=True))
    assert num_sub_live == len(node.subcommands())

    assert 0 == len(node.references())


@pytest.mark.parametrize(
    ["node", "num_ref_live", "num_ref_all"],
    [
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
            ),
            0,
            0,
            id="empty"
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo", reference=ReferenceSubcommand("pkg")),
                ],
            ),
            1,
            1,
            id="single",
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo", reference=ReferenceSubcommand("pkg")),
                    LayoutNode("foo", "bar", reference=ReferenceSubcommand("pkg"), bugs=["1"]),
                ],
            ),
            1,
            2,
            id="multi",
        ),
        pytest.param(
            LayoutNode(
                command="foo",
                identifier="bar",
                children=[
                    LayoutNode("sna", "foo", reference=ReferenceSubcommand("pkg")),
                    LayoutNode("more", "work"),
                    LayoutNode("foo", "bar", reference=ReferenceSubcommand("pkg")),
                    LayoutNode("even", "more", reference=ReferenceSubcommand("pkg", "app"), bugs=["abc"]),
                ],
            ),
            2,
            3,
            id="full",
        ),
    ]
)
def test_node_references(node, num_ref_live, num_ref_all):
    assert num_ref_live == len(node.references())
    assert num_ref_all == len(node.references(include_all=True))


@pytest.mark.parametrize(
    ["page_names", "expected"],
    [
        pytest.param(PaginationNames(), False, id="empty"),
        pytest.param(PaginationNames(page_size="per-page"), True, id="page-size"),
        pytest.param(PaginationNames(page_start="start"), True, id="page-start"),
        pytest.param(PaginationNames(item_start="offset"), True, id="item-start"),
        pytest.param(PaginationNames(next_header="next"), True, id="next-header"),
        pytest.param(PaginationNames(next_property="next"), True, id="next-prop"),
        pytest.param(PaginationNames(items_property="data"), False, id="items-prop"),
        pytest.param(
            PaginationNames(
                page_size="page",
                page_start="start",
                item_start="offset",
                items_property="data",
                next_header="next",
                next_property="next"),
            True,
            id="all",
        ),
    ]
)
def test_page_parameters_sizeable(page_names, expected):
    assert page_names.sizeable() == expected
