"""Functions to merge two layouts together with."""
from copy import deepcopy

from openapi_spec_tools.layout.types import LayoutNode


def operations_to_node(node: LayoutNode) -> dict[str, str]:
    """Create map of operationId to parent LayoutNode."""
    result = {node.identifier: node}
    for child in node.children:
        result.update(operations_to_node(child))

    return result



def merge(original: LayoutNode, suggested: LayoutNode) -> LayoutNode:
    """Merge data from suggested into original."""
    updated = deepcopy(suggested)
    up_ops = operations_to_node(updated)
    orig_ops = operations_to_node(original)

    for op_id, up_op in up_ops.items():
        orig_op = orig_ops.get(op_id)
        if not orig_op:
            continue

        up_op.copy_data(orig_op)

    return updated
