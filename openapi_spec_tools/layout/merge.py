"""Functions to merge two layouts together with."""
from copy import deepcopy

from openapi_spec_tools.layout.types import LayoutNode


def operations_to_node(node: LayoutNode) -> dict[str, str]:
    """Create map of operationId to parent LayoutNode."""
    result = {node.identifier: node}
    for child in node.children:
        result.update(operations_to_node(child))

    return result


def operations_to_parent(node: LayoutNode) -> dict[str, LayoutNode]:
    """Map operations to their parents."""
    result = {}
    for child in node.children:
        result[child.identifier] = node
        result.update(operations_to_parent(child))
    return result


def find_peers(node: LayoutNode, op_id: str) -> list[str]:
    """Find something that is a peer of the specified op_id."""
    op_ids = [_.identifier for _ in node.children]
    if op_id in op_ids:
        return [_ for _ in op_ids if _ != op_id]

    for child in node.children:
        op_ids = find_peers(child, op_id)
        if op_ids:
            return op_ids

    return []


def merge(original: LayoutNode, suggested: LayoutNode) -> LayoutNode:
    """Merge data from suggested into original."""
    updated = deepcopy(original)
    up_parents = operations_to_parent(updated)
    up_ops = operations_to_node(updated)
    sugg_ops = operations_to_node(suggested)
    sugg_parents = operations_to_parent(suggested)

    # prune the items no longer in use
    to_remove = [op_id for op_id, up_op in up_ops.items() if op_id not in sugg_ops and not up_op.children]
    for op_id in to_remove:
        # walk back up the parent tree until there are other children
        remove_id = op_id
        while remove_id:
            parent = up_parents.get(remove_id)
            parent.children = [child for child in parent.children if child.identifier != remove_id]
            remove_id = None if parent.children else parent.identifier

    # add missing operations
    to_add = [op_id for op_id, sugg_op in sugg_ops.items() if op_id not in up_ops and not sugg_op.children]
    for op_id in to_add:
        add_id = op_id
        # walk back up the parent tree until we find something
        while add_id:
            # find the peers in the suggested, so we can try to find similar in the updated
            sugg_peers = find_peers(suggested, add_id)
            sugg_op = sugg_ops.get(add_id)
            added = False
            for peer_id in sugg_peers:
                up_parent = up_parents.get(peer_id)
                if up_parent:
                    children = up_parent.children
                    # need to check because of way parents are added
                    if add_id not in [_.identifier for _ in children]:
                        up_parent.children = sorted(children + [sugg_op], key=lambda x: x.command)
                    added = True
                    break

            # stop the walk if something was added, otherwise get the parent
            add_id = None if added else sugg_parents.get(add_id).identifier

    return updated
