#!/usr/bin/env python3
import os

import typer
from typing_extensions import Annotated

from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import DEFAULT_START
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.cli_gen.layout_types import CommandNode
from oas_tools.cli_gen.utils import to_snake_case
from oas_tools.utils import open_oas

#################################################
# Top-level stuff
app = typer.Typer(
    help="Various utilities for inspecting, analyzing and modifying CLI layout file.",
)


def generate_node(generator: Generator, node: CommandNode, directory: str) -> None:
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


@app.command()
def generate_cli(
    layout_file: Annotated[str, typer.Argument(help="Layout file name")],
    openapi_file: Annotated[str, typer.Argument(help="OpenAPI specification filename")],
    package_name: Annotated[str, typer.Argument(help="Base package name")],
    directory: Annotated[str, typer.Argument(help="Directory name")],
    start: Annotated[str, typer.Option(help="Start point in layout file")] = DEFAULT_START,
) -> None:
    commands = file_to_tree(layout_file, start=start)
    oas = open_oas(openapi_file)

    os.makedirs(directory, exist_ok=True)

    generator = Generator(package_name, oas)
    generate_node(generator, commands, directory)
    typer.echo(f"Generated files in {directory}")


if __name__ == "__main__":
    app()
