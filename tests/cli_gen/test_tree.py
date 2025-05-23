from oas_tools.cli_gen._tree import TreeDisplay
from oas_tools.cli_gen._tree import TreeNode


def test_tree_node_get():
    node = TreeNode(
        name="myName",
        help="not helpful",
        operation="pysops",
        function="disfunction",
        method="madness",
        path="narrow",
    )
    assert "myName" == node.name()
    assert [] == node.children()

    assert "not helpful" == node.get(TreeDisplay.HELP)
    assert "pysops" == node.get(TreeDisplay.OPERATION)
    assert "disfunction" == node.get(TreeDisplay.FUNCTION)
    assert "MADNESS narrow" == node.get(TreeDisplay.PATH)
    assert node.get(TreeDisplay.ALL) is None
