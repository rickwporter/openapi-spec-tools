#!/usr/bin/env python3
import os
from enum import Enum
from typing import Optional

import typer
import yaml
from rich import print_json
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from oas_tools.cli_gen._arguments import LogLevelOption
from oas_tools.cli_gen._logging import init_logging
from oas_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from oas_tools.cli_gen.generate import check_for_missing
from oas_tools.cli_gen.generate import copy_infrastructure
from oas_tools.cli_gen.generate import copy_tests
from oas_tools.cli_gen.generate import find_unreferenced
from oas_tools.cli_gen.generate import generate_node
from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import DEFAULT_START
from oas_tools.cli_gen.layout import check_pagination_definitions
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.cli_gen.layout import open_layout
from oas_tools.cli_gen.layout import operation_duplicates
from oas_tools.cli_gen.layout import operation_order
from oas_tools.cli_gen.layout import subcommand_missing_properties
from oas_tools.cli_gen.layout import subcommand_order
from oas_tools.cli_gen.layout import subcommand_references
from oas_tools.cli_gen.layout_types import LayoutNode
from oas_tools.types import OasField
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
app = typer.Typer(
    no_args_is_help=True,
    help="Various operations for CLI generation."
)
app.add_typer(layout)



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
    pagination: Annotated[bool, typer.Option(help="Check the pagination parameters for issues")] = True,
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


@app.command("generate", short_help="Generate CLI code")
def generate_cli(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    package_name: Annotated[str, typer.Argument(show_default=False, help="Base package name")],
    project_dir: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="Project directory name")
    ] = None,
    code_dir: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="Directory for code -- overrides default")
    ] = None,
    test_dir: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="Directory for tests -- overrides default")
    ] = None,
    include_tests: Annotated[bool, typer.Option("--tests/--no-tests", help="Include tests in generated coode")] = True,
    start: StartPointOption = DEFAULT_START,
    log_level: LogLevelOption = "DEBUG",
) -> None:
    """
    Generates CLI code based on the provided parameters.

    Use either `--project-dir` to set both relative code and test directories, or
    set the paths specifically using `--code-dir` and `--test-dir`.
    """
    init_logging(log_level, GENERATOR_LOG_CLASS)

    if project_dir:
        code_dir = code_dir or os.path.join(project_dir, package_name)
        test_dir = test_dir or os.path.join(project_dir, "tests")
    else:
        if not code_dir:
            typer.echo(
                "Must provide code directory using either `--project-dir` (which uses package"
                " name), or `--code-dir`"
            )
            raise typer.Exit(1)
        if not test_dir and include_tests:
            typer.echo(
                "Must provide test directory using either `--project-dir` (which uses "
                "tests sub-directory), or `--tests-dir`"
            )
            raise typer.Exit(1)

    commands = file_to_tree(layout_file, start=start)
    oas = open_oas(openapi_file)

    missing = check_for_missing(commands, oas)
    if missing:
        typer.echo(render_missing(missing))
        raise typer.Exit(1)

    os.makedirs(code_dir, exist_ok=True)

    # create the init file
    init_file = os.path.join(code_dir, '__init__.py')
    with open(init_file, "w"):
        pass

    # copy over the basic infrastructure
    copy_infrastructure(code_dir, package_name)

    generator = Generator(package_name, oas)
    generate_node(generator, commands, code_dir)

    if include_tests:
        os.makedirs(test_dir, exist_ok=True)
        copy_tests(test_dir,  package_name)

    typer.echo("Generated files")


@app.command("check", help="Check OAS contains layout operations")
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


@app.command("unreferenced", help="Look for operation in OAS not referenced byt layout")
def generate_unreferenced(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    full_path: Annotated[bool, typer.Option(help="Use full URL path that included variables")] = False,
) -> None:
    commands = file_to_tree(layout_file, start=start)
    oas = open_oas(openapi_file)

    unreferenced = find_unreferenced(commands, oas)
    if not unreferenced:
        typer.echo("No unreferenced operations found")
        return

    # group by path
    paths = {}
    for op in unreferenced.values():
        path = op.get(OasField.X_PATH)
        if not full_path:
            # remove the variable elements from the path
            parts = path.split("/")
            path = "/".join([p for p in parts if p and '{' not in p])

        operations = paths.get(path, [])
        operations.append(op)
        paths[path] = operations

    # display each operations below the path
    for path, ops in paths.items():
        typer.echo(path)
        for op in ops:
            typer.echo(f"  - {op.get(OasField.OP_ID)}")

    typer.echo(f"\nFound {len(unreferenced)} operations in {len(paths)} paths")


if __name__ == "__main__":
    app()
