from enum import Enum
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic import Field
from rich.panel import Panel
from rich.table import Table
from rich_objects import console_factory

INDENT = "  "


class TreeDisplay(str, Enum):
    HELP = "help"
    FUNCTION = "function"
    OPERATION = "operation"
    PATH = "path"
    ALL = "all"


class TreeField(str, Enum):
    OPERATIONS = "operations"
    DESCRIPTION = "description"

    NAME = "name"
    OP_ID = "operationId"
    METHOD = "method"
    HELP = "help"
    PATH = "path"
    SUB_CMD = "subcommandId"
    FUNC = "function"
    MODULE = "module"


class TreeNode(BaseModel):
    """Represention of the relationship between the CLI and OAS.

    The structure is picked up from the layout file, and details about help, path, etc
    come from the OAS.
    """

    name: str
    help: Optional[str] = None
    operation: Optional[str] = None
    function: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    children: list["TreeNode"] = Field(default_factory=list)

    def get(self, display: TreeDisplay) -> str:
        if display == TreeDisplay.HELP:
            return self.help or ''
        if display == TreeDisplay.FUNCTION:
            return self.function or ''
        if display == TreeDisplay.OPERATION:
            return self.operation or ''
        if display == TreeDisplay.PATH:
            return f"{self.method.upper():6} {self.path}" if self.path else ''
        return None

    def contains(self, needle: str) -> bool:
        """Check if the needle is found in this node, or any children."""
        def _has_needle(value: Optional[str]) -> bool:
            return value and needle in value

        if any(_has_needle(p) for p in [self.name, self.help, self.function, self.operation, self.path, self.method]):
            return True

        if any(c.contains(needle) for c in self.children):
            return True

        return False


def parse_tree(identifier: str, command: str, data: dict[str, dict]) -> Optional[TreeNode]:
    """Parse the specified file into a tree."""
    item = data.get(identifier)
    children = []
    for operation in item.get(TreeField.OPERATIONS, []):
        child_name = operation.get(TreeField.NAME)
        sub_command = operation.get(TreeField.SUB_CMD)
        if sub_command:
            child = parse_tree(sub_command, child_name, data)
            children.append(child)
        else:
            children.append(
                TreeNode(
                    name=child_name,
                    help=operation.get(TreeField.HELP),
                    operation=operation.get(TreeField.OP_ID),
                    function=operation.get(TreeField.FUNC),
                    method=operation.get(TreeField.METHOD),
                    path=operation.get(TreeField.PATH),
                )
            )

    return TreeNode(
        name=command + '*',
        help=item.get(TreeField.DESCRIPTION),
        children=children,
    )


def create_node_table(node: TreeNode) -> Table:
    """Create the "inner" table for an individual node."""
    table = Table(
        highlight=True,
        show_header=False,
        show_lines=False,
        show_edge=False,
        row_styles=None,
        expand=False,
        caption_justify="left",
        border_style=None,
        leading=0,
        pad_edge=False,
        padding=(0, 1),
        box=None,
    )
    table.add_column("Property", justify="left", no_wrap=True, overflow="ignore")
    table.add_column("Value", justify="left", no_wrap=True, overflow="ignore")
    for display in [TreeDisplay.HELP, TreeDisplay.OPERATION, TreeDisplay.PATH, TreeDisplay.FUNCTION]:
        value = node.get(display)
        if value:
            table.add_row(display.value, value)

    return table


def add_node_to_table(
    table: Table,
    node: TreeNode,
    display: TreeDisplay,
    depth: int,
    max_depth: int,
    needle: Optional[str],
) -> None:
    """Add a node (with children) to the table."""
    indent = INDENT * depth
    if display != TreeDisplay.ALL:
        content = node.get(display)
    else:
        content = create_node_table(node)

    table.add_row(indent + node.name, content)
    if max_depth > depth:
        for child in node.children:
            if needle and not child.contains(needle):
                continue

            add_node_to_table(table, child, display, depth + 1, max_depth, needle)

    return


def create_tree_table(
    node: TreeNode,
    display: TreeDisplay,
    max_depth: int,
    needle: Optional[str] = None,
) -> Table:
    """Create the tree table.

    It is a "flat" table where the left column is the commands with each child being
    indented another level beyond the parent. The right column is either a single property,
    or a table of properties.
    """
    table = Table(
        highlight=False,
        show_header=False,
        expand=False,
        box=None,
        show_lines=False,
        leading=0,
        border_style=None,
        row_styles=None,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column(display.value.title())
    for child in node.children:
        if needle and not child.contains(needle):
            continue

        add_node_to_table(table, child, display, 0, max_depth, needle)

    return table


def tree(filename: str, identifier: str, display: TreeDisplay, max_depth: int, needle: Optional[str] = None) -> None:
    """Print the tree table for the specified command."""
    with open(filename, "r", encoding="utf-8", newline="\n") as fp:
        data = yaml.safe_load(fp)

    console = console_factory()

    # parse into the tree format
    node = parse_tree(identifier, identifier, data)
    if needle and not node.contains(needle):
        console.print(f"No '{needle}' matches found.")
        return

    table = create_tree_table(node, display, max_depth, needle)
    panel = Panel(table, border_style="dim", title="Command Tree", title_align="left")
    console.print(panel)
