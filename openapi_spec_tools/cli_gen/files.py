"""Implementation for creating/copying CLI files."""
from typing import Any

from openapi_spec_tools.cli_gen._tree import TreeField
from openapi_spec_tools.cli_gen._tree import TreeNode
from openapi_spec_tools.cli_gen.cli_generator import CliGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations


def generate_tree_node(generator: CliGenerator, node: LayoutNode) -> TreeNode:
    """Generate a TreeNode hierarchy for the specified node."""
    data = generator.tree_data(node)
    children = []
    for item in data.get(TreeField.OPERATIONS, []):
        op_id = item.get(TreeField.OP_ID)
        if not op_id:
            continue
        op = TreeNode(
            name=item.get(TreeField.NAME),
            help=item.get(TreeField.HELP),
            operation=item.get(TreeField.OP_ID),
            function=item.get(TreeField.FUNC),
            method=item.get(TreeField.METHOD),
            path=item.get(TreeField.PATH),
        )
        children.append(op)

    for sub in node.subcommands():
        children.append(generate_tree_node(generator, sub))

    return TreeNode(
        name=data.get(TreeField.NAME),
        help=data.get(TreeField.DESCRIPTION),
        children=children,
    )


def check_for_missing(node: LayoutNode, oas: dict[str, Any]) -> dict[str, list[str]]:
    """Look for operations in node (and children) that are NOT in the OpenAPI spec."""
    def _check_missing(node: LayoutNode, ops: dict[str, Any]) -> dict[str, list[str]]:
        current = []
        for op in node.operations():
            if op.identifier not in operations:
                current.append(op.identifier)

        if not current:
            return {}
        return {node.identifier: current}


    operations = map_operations(oas.get(OasField.PATHS, {}))
    missing = _check_missing(node, operations)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        missing.update(_check_missing(command, operations))

    return missing


def find_unreferenced(node: LayoutNode, oas: dict[str, Any]) -> dict[str, Any]:
    """Find the operations in the OAS that are unrerenced by the commands."""
    def _find_operations(_node: LayoutNode) -> set[str]:
        """Recursively finds all the operations for this node and it's children."""
        current = set()
        for op in _node.operations(include_all=True):
            current.add(op.identifier)
        for child in _node.subcommands(include_all=True):
            current.update(_find_operations(child))
        return current

    referenced = _find_operations(node)
    ops = map_operations(oas.get(OasField.PATHS))
    unreferenced = {
        op_id: op_data
        for op_id, op_data in ops.items()
        if op_id not in referenced
    }

    return unreferenced
