import pytest

from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
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
            LayoutNode(command="create", identifier="createPets", summary_fields=["name"]),
            id="child",
        ),
    ]
)
def test_node_find(search_args, expected) -> None:
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    assert expected == tree.find(*search_args)


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
