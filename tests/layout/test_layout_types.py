import pytest

from openapi_spec_tools.layout.types import LayoutNode
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
