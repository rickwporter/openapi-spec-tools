#!/usr/bin/env python3
"""Implement the 'layout' CLI."""
from datetime import datetime
from enum import Enum
from typing import Annotated

import typer
import yaml
from rich import print
from rich import print_json
from rich.table import Table

from openapi_spec_tools.cli._arguments import LayoutFilenameArgument
from openapi_spec_tools.cli._arguments import LogLevelOption
from openapi_spec_tools.cli._arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli._arguments import StartPointOption
from openapi_spec_tools.cli._utils import console_factory
from openapi_spec_tools.cli._utils import init_logging
from openapi_spec_tools.cli._utils import layout_tree_with_error_handling
from openapi_spec_tools.cli._utils import open_layout_with_error_handling
from openapi_spec_tools.cli._utils import open_oas_with_error_handling
from openapi_spec_tools.layout.layout_generator import LayoutGenerator
from openapi_spec_tools.layout.layout_generator import write_layout
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import DEFAULT_START
from openapi_spec_tools.layout.utils import check_pagination_definitions
from openapi_spec_tools.layout.utils import operation_duplicates
from openapi_spec_tools.layout.utils import operation_order
from openapi_spec_tools.layout.utils import subcommand_missing_properties
from openapi_spec_tools.layout.utils import subcommand_order
from openapi_spec_tools.layout.utils import subcommand_references

SEP = "\n    "
LOG_CLASS = "layout"

app = typer.Typer(
    name="layout",
    no_args_is_help=True,
    help="Various utilities for inspecting, analyzing and modifying CLI layout file.",
)

#################################################
# Layout stuff
@app.command(
    "check",
    short_help="Check formatting of layout file"
)
def layout_check_format(
    filename: LayoutFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    references: Annotated[bool, typer.Option(help="Check for missing and unused subcommands")] = True,
    sub_order: Annotated[bool, typer.Option(help="Check the sub-command order")] = True,
    missing_props: Annotated[bool, typer.Option(help="Check for missing properties")] = True,
    op_dups: Annotated[bool, typer.Option(help="Check for duplicate names in sub-commands")] = True,
    op_order: Annotated[bool, typer.Option(help="Check the operations order within each sub-command")] = True,
    pagination: Annotated[bool, typer.Option(help="Check the pagination parameters for issues")] = True,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    data = open_layout_with_error_handling(filename, logger)

    def _dict_to_str(errors: dict[str, str], sep=SEP) -> str:
        return f"{sep}{sep.join([f'{k}: {v}' for k, v in errors.items()])}"

    result = 0
    if references:
        unused, missing = subcommand_references(data, start)
        if missing:
            typer.echo(f"Missing sub-commands for:{SEP}{SEP.join(missing)}")
            result = 1

        if unused:
            typer.echo(f"Unused sub-commands for:{SEP}{SEP.join(unused)}")
            result = 1

    if sub_order:
        errors = subcommand_order(data, start)
        if errors:
            typer.echo(f"Sub-commands are misordered:{SEP}{SEP.join(errors)}")
            result = 1

    if missing_props:
        errors = subcommand_missing_properties(data)
        if errors:
            typer.echo(f"Sub-commands have missing properties:{_dict_to_str(errors)}")
            result = 1

    if op_dups:
        errors = operation_duplicates(data)
        if errors:
            typer.echo(f"Duplicate operations in sub-commands:{_dict_to_str(errors)}")
            result = 1

    if op_order:
        errors = operation_order(data)
        if errors:
            typer.echo(f"Sub-command operation orders should be:{_dict_to_str(errors)}")
            result = 1

    if pagination:
        errors = check_pagination_definitions(data)
        if errors:
            typer.echo(f"Pagination parameter errors:{_dict_to_str(errors)}")
            result = 1

    if result:
        raise typer.Exit(result)

    typer.echo(f"No errors found in {filename}")
    return


class TreeFormat(str, Enum):
    """Display options for show the tree output."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"


@app.command(
    "tree",
    short_help="Display the tree of commands"
)
def layout_tree(
    filename: LayoutFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    style: Annotated[TreeFormat, typer.Option(case_sensitive=False, help="Output style")] = TreeFormat.TEXT,
    indent: Annotated[int, typer.Option(min=1, max=10, help="Number of characters of indent")] = 2,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    tree = layout_tree_with_error_handling(filename, start=start, logger=logger)
    if style == TreeFormat.JSON:
        print_json(data=tree.as_dict(), indent=indent, sort_keys=False)
        return

    if style == TreeFormat.YAML:
        print(yaml.dump(tree.as_dict(), indent=indent, sort_keys=False))
        return

    def add_node(table: Table, node: LayoutNode, level: int) -> None:
        name = f"{' ' * indent * level}{node.command}"
        table.add_row(name, node.identifier, node.description)
        for child in node.children:
            add_node(table, child, level + 1)

    table = Table(
        highlight=True,
        expand=False,
        leading=0,
        show_header=True,
        show_edge=True,
    )
    headers = ["Command", "Identifier", "Help"]
    for name in headers:
        table.add_column(name, justify="left", no_wrap=True, overflow="ignore")

    add_node(table, tree, 0)
    console = console_factory()
    console.print(table)
    return


@app.command(
    "operations",
    short_help="List all operationIds referenced"
)
def layout_operations(
    filename: LayoutFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    log_level: LogLevelOption = "info",
) -> None:
    """Get a list of opertionId's used in the specified layout file."""
    def _operations(_node: LayoutNode) -> set[str]:
        ops = {op.identifier for op in _node.operations()}
        for sub in _node.subcommands():
            ops.update(_operations(sub))
        return ops

    logger = init_logging(log_level, LOG_CLASS)
    tree = layout_tree_with_error_handling(filename, start=start, logger=logger)
    operations = _operations(tree)
    print('\n'.join(sorted(operations)))
    return


@app.command(
    "suggest",
    short_help="Suggest layout based on OpenAPI spec"
)
def layout_suggest(
    openapi_file: OpenApiFilenameArgument,
    output_file: Annotated[str, typer.Argument(show_default=False, help="File name for output")],
    prefix: Annotated[str, typer.Option(show_default=False, help="Prefix common to all paths")] = "",
    log_level: LogLevelOption = "info",
) -> None:
    """Create a suggested layout based on the OpenAPI spec paths and operations.

    This is a way to quick-start creating a layout file, but has a few issues:

    * May have duplicate commands that may need to be fixed (detected with `layout check`)

    * Does not consider pagaination

    * May have some small modules (extra layers), such as `deploy list` instead of a desired `deploy`.
    """
    logger = init_logging(log_level, LOG_CLASS)
    oas = open_oas_with_error_handling(openapi_file, logger)
    generator = LayoutGenerator()
    node = generator.generate(oas, prefix)

    start = datetime.now()
    write_layout(output_file, node)
    delta = datetime.now() - start
    logger.info(f"Writing {output_file} took {delta.total_seconds()} seconds")
    print(f"Wrote {output_file}")
    return


if __name__ == "__main__":
    app()
