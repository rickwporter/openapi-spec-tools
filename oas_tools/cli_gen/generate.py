#!/usr/bin/env python3
import os
from typing import Any

import typer
from typing_extensions import Annotated

from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import DEFAULT_START
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.cli_gen.layout_types import CommandNode
from oas_tools.cli_gen.utils import to_snake_case
from oas_tools.types import OasField
from oas_tools.utils import map_operations
from oas_tools.utils import open_oas

#################################################
# Top-level stuff
app = typer.Typer(
    no_args_is_help=True,
    help="Various utilities for working with OpenAPI specs with the CLI layout file.",
)


def render_missing(missing: dict[str, list[str]]) -> str:
    sep = "\n    "
    return (
        f"Commands with missing operations:{sep}" +
        sep.join(f"{cmd}: {', '.join(ops)}" for cmd, ops in missing.items())
    )


def generate_node(generator: Generator, node: CommandNode, directory: str) -> None:
    """Creates a file/module for the current node, and recursively goes through sub-commands."""
    text = generator.shebang()
    text += generator.copyright()
    text += generator.standard_imports()
    text += generator.subcommand_imports(node.subcommands())
    text += generator.app_definition(node)
    for command in node.operations():
        text += generator.function_definition(command)
    text += generator.main()

    filename = os.path.join(directory, to_snake_case(node.identifier) + ".py")
    with open(filename, "w") as fp:
        fp.write(text)
    os.chmod(filename, 0o755)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        generate_node(generator, command, directory)


def check_for_missing(node: CommandNode, oas: dict[str, Any]) -> dict[str, list[str]]:
    """Look for operations in node (and children) that are NOT in the OpenAPI spec"""
    def _check_missing(node: CommandNode, ops: dict[str, Any]) -> dict[str, list[str]]:
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


@app.command("generate", help="Generate CLI code")
def generate_cli(
    layout_file: Annotated[str, typer.Argument(show_default=False, help="Layout file name")],
    openapi_file: Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")],
    package_name: Annotated[str, typer.Argument(show_default=False, help="Base package name")],
    directory: Annotated[str, typer.Argument(show_default=False, help="Directory name")],
    start: Annotated[str, typer.Option(help="Start point in layout file")] = DEFAULT_START,
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


@app.command("check", help="Check OAS contains layout operations")
def generate_check_missing(
    layout_file: Annotated[str, typer.Argument(show_default=False, help="Layout file name")],
    openapi_file: Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")],
    start: Annotated[str, typer.Option(help="Start point in layout file")] = DEFAULT_START,
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
