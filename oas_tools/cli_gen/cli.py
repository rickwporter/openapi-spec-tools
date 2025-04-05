#!/usr/bin/env python3
import os
from enum import Enum

import typer
import yaml
from rich import print_json
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from oas_tools.cli_gen.generate import check_for_missing
from oas_tools.cli_gen.generate import generate_node
from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import DEFAULT_START
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.cli_gen.layout import open_layout
from oas_tools.cli_gen.layout import operation_duplicates
from oas_tools.cli_gen.layout import operation_order
from oas_tools.cli_gen.layout import subcommand_missing_properties
from oas_tools.cli_gen.layout import subcommand_order
from oas_tools.cli_gen.layout import subcommand_references
from oas_tools.cli_gen.layout_types import CommandNode
from oas_tools.utils import open_oas

SEP = "\n    "

LayoutFilenameArgument = Annotated[str, typer.Argument(show_default=False , help="Layout file YAML definition")]
OpenApiFilenameArgument = Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")]
StartPointOption = Annotated[str, typer.Option(help="Start point for CLI in layout file")]

#################################################
# Top-level stuff
layout = typer.Typer(
    name="layout",
    no_args_is_help=True,
    help="Various utilities for inspecting, analyzing and modifying CLI layout file.",
)
generate = typer.Typer(
    name="generate",
    no_args_is_help=True,
    help="Various utilities for working with OpenAPI specs with the CLI layout file.",
)
app = typer.Typer(
    no_args_is_help=True,
    help="Various operations for CLI generation."
)
app.add_typer(layout)
app.add_typer(generate)



#################################################
# Layout stuff
@layout.command(
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
) -> None:
    data = open_layout(filename)

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

    if result:
        raise typer.Exit(result)

    typer.echo(f"No errors found in {filename}")
    return


class TreeFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"


@layout.command(
    "tree",
    short_help="Display the tree of commands"
)
def layout_tree(
    filename: LayoutFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    style: Annotated[TreeFormat, typer.Option(case_sensitive=False, help="Output style")] = TreeFormat.TEXT,
    indent: Annotated[int, typer.Option(min=1, max=10, help="Number of characters of indent")] = 2,
) -> None:
    tree = file_to_tree(filename, start=start)
    if style == TreeFormat.JSON:
        print_json(data=tree.as_dict(), indent=indent, sort_keys=False)
        return

    if style == TreeFormat.YAML:
        print(yaml.dump(tree.as_dict(), indent=indent, sort_keys=False))
        return

    def add_node(table: Table, node: CommandNode, level: int) -> None:
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
    console = Console()
    console.print(table)
    return


#################################################
# Generate stuff

def render_missing(missing: dict[str, list[str]]) -> str:
    return (
        f"Commands with missing operations:{SEP}" +
        SEP.join(f"{cmd}: {', '.join(ops)}" for cmd, ops in missing.items())
    )


@generate.command("generate", help="Generate CLI code")
def generate_cli(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    package_name: Annotated[str, typer.Argument(show_default=False, help="Base package name")],
    directory: Annotated[str, typer.Argument(show_default=False, help="Directory name")],
    start: StartPointOption = DEFAULT_START,
) -> None:
    commands = file_to_tree(layout_file, start=start)
    oas = open_oas(openapi_file)

    missing = check_for_missing(commands, oas)
    if missing:
        typer.echo(render_missing(missing))
        raise typer.Exit(1)

    os.makedirs(directory, exist_ok=True)

    generator = Generator(package_name, oas)
    generate_node(generator, commands, directory)
    typer.echo(f"Generated files in {directory}")


@generate.command("check", help="Check OAS contains layout operations")
def generate_check_missing(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    start: StartPointOption = DEFAULT_START,
) -> None:
    commands = file_to_tree(layout_file, start=start)
    oas = open_oas(openapi_file)

    missing = check_for_missing(commands, oas)
    if missing:
        typer.echo(render_missing(missing))
        raise typer.Exit(1)

    typer.echo(f"All operations in {layout_file} found in {openapi_file}")


if __name__ == "__main__":
    app()
