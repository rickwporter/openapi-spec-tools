#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Optional

import typer
import yaml
from rich import print_json
from rich.console import Console
from rich.table import Table

from openapi_spec_tools.cli_gen._arguments import LogLevelOption
from openapi_spec_tools.cli_gen._logging import get_logger
from openapi_spec_tools.cli_gen._logging import init_logging
from openapi_spec_tools.cli_gen._tree import TreeDisplay
from openapi_spec_tools.cli_gen._tree import create_tree_table
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.cli_gen.files import check_for_missing
from openapi_spec_tools.cli_gen.files import copy_infrastructure
from openapi_spec_tools.cli_gen.files import copy_tests
from openapi_spec_tools.cli_gen.files import find_unreferenced
from openapi_spec_tools.cli_gen.files import generate_node
from openapi_spec_tools.cli_gen.files import generate_tree_file
from openapi_spec_tools.cli_gen.files import generate_tree_node
from openapi_spec_tools.cli_gen.files import set_copyright
from openapi_spec_tools.cli_gen.generator import Generator
from openapi_spec_tools.cli_gen.layout import DEFAULT_START
from openapi_spec_tools.cli_gen.layout import check_pagination_definitions
from openapi_spec_tools.cli_gen.layout import file_to_tree
from openapi_spec_tools.cli_gen.layout import open_layout
from openapi_spec_tools.cli_gen.layout import operation_duplicates
from openapi_spec_tools.cli_gen.layout import operation_order
from openapi_spec_tools.cli_gen.layout import subcommand_missing_properties
from openapi_spec_tools.cli_gen.layout import subcommand_order
from openapi_spec_tools.cli_gen.layout import subcommand_references
from openapi_spec_tools.cli_gen.layout_types import LayoutNode
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import open_oas
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required

SEP = "\n    "

LayoutFilenameArgument = Annotated[str, typer.Argument(show_default=False , help="Layout file YAML definition")]
OpenApiFilenameArgument = Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")]
StartPointOption = Annotated[str, typer.Option(help="Start point for CLI in layout file")]


#################################################
# Utilities
def open_oas_with_error_handling(filename: str) -> Any:
    """Perform error handling around opening an OpenAPI spec.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        data = open_oas(filename)
        delta = datetime.now() - starttime
        get_logger(GENERATOR_LOG_CLASS).info(f"Opening {filename} took {delta.total_seconds()} seconds")
        return data
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


def open_layout_with_error_handling(filename: str) -> Any:
    """Perform error handling around opening a layout file.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        data = open_layout(filename)
        delta = datetime.now() - starttime
        get_logger(GENERATOR_LOG_CLASS).info(f"Opening {filename} took {delta.total_seconds()} seconds")
        return data
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


def layout_tree_with_error_handling(filename: str, start: str) -> LayoutNode:
    """Perform error handling around opening a layout file.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        tree = file_to_tree(filename, start)
        delta = datetime.now() - starttime
        get_logger(GENERATOR_LOG_CLASS).info(f"Parsing {filename} into tree took {delta.total_seconds()} seconds")
        return tree
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except ValueError as ex:
        message = str(ex)
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


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
    data = open_layout_with_error_handling(filename)

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
    tree = layout_tree_with_error_handling(filename, start=start)
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


@layout.command(
    "operations",
    short_help="List all operationIds referenced"
)
def layout_operations(
    filename: LayoutFilenameArgument,
    start: StartPointOption = DEFAULT_START,
) -> None:
    """Get a list of opertionId's used in the specified layout file."""
    def _operations(_node: LayoutNode) -> set[str]:
        ops = {op.identifier for op in _node.operations()}
        for sub in _node.subcommands():
            ops.update(_operations(sub))
        return ops

    tree = layout_tree_with_error_handling(filename, start=start)
    operations = _operations(tree)
    print('\n'.join(sorted(operations)))
    return


#################################################
# Generate stuff

def render_missing(missing: dict[str, list[str]]) -> str:
    """Pretty-print string of dictionary of missing items."""
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
    copyright_file: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="File name containing copyright message (for non-default)"),
    ] = None,
    include_tests: Annotated[bool, typer.Option("--tests/--no-tests", help="Include tests in generated coode")] = True,
    start: StartPointOption = DEFAULT_START,
    log_level: LogLevelOption = "info",
) -> None:
    """Generate CLI code based on the provided parameters.

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

    commands = layout_tree_with_error_handling(layout_file, start=start)
    oas = open_oas_with_error_handling(openapi_file)

    if copyright_file:
        text = Path(copyright_file).read_text()
        set_copyright(text)

    missing = check_for_missing(commands, oas)
    if missing:
        typer.echo(render_missing(missing))
        raise typer.Exit(1)

    os.makedirs(code_dir, exist_ok=True)

    # create the init file
    init_file = os.path.join(code_dir, '__init__.py')
    with open(init_file, "w", encoding="utf-8", newline="\n"):
        # do not bother writing anything to init file
        pass

    # copy over the basic infrastructure
    copy_infrastructure(code_dir, package_name)

    generator = Generator(package_name, oas)
    generate_node(generator, commands, code_dir)

    # create the tree
    generate_tree_file(generator, commands, code_dir)

    if include_tests:
        os.makedirs(test_dir, exist_ok=True)
        copy_tests(test_dir, package_name, start)

    typer.echo("Generated files")


@app.command("check", help="Check OAS contains layout operations")
def generate_check_missing(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level, GENERATOR_LOG_CLASS)
    commands = layout_tree_with_error_handling(layout_file, start=start)
    oas = open_oas_with_error_handling(openapi_file)

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
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level, GENERATOR_LOG_CLASS)
    commands = layout_tree_with_error_handling(layout_file, start=start)
    oas = open_oas_with_error_handling(openapi_file)

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


@app.command("tree", help="Displays the CLI tree")
def show_cli_tree(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    display: Annotated[
        TreeDisplay,
        typer.Option(case_sensitive=False, help="Details to show about tree")
    ] = TreeDisplay.ALL,
    max_depth: Annotated[int, typer.Option(help="Maximum tree depth to show")] = 10,
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level, GENERATOR_LOG_CLASS)
    layout = layout_tree_with_error_handling(layout_file, start=start)
    oas = open_oas_with_error_handling(openapi_file)
    generator = Generator("", oas)

    tree = generate_tree_node(generator, layout)
    if not tree.children:
        typer.echo("No operations or sub-commands found")
        return

    table = create_tree_table(tree, display, max_depth)
    table.show_header = True
    table.expand = False
    console = Console()
    console.print(table)


@app.command(
    "trim",
    short_help="Create an OpenAPI spec that only contains data referenced by layout"
)
def trim_oas(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    updated_file: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="Filename for updated OpenAPI spec, overwrites original of not specified.",
        ),
    ] = None,
    remove_properties: Annotated[
        Optional[list[str]],
        typer.Option("--remove", show_default=False, help="List of properties to remove."),
    ] = None,
    start: StartPointOption = DEFAULT_START,
    nullable_not_required: Annotated[
        bool,
        typer.Option(help="Remove 'nullable' properties from required list"),
    ] = True,
    remove_all_tags: Annotated[bool, typer.Option(help="Remove all tags")] = True,
    indent: Annotated[
        int,
        typer.Option(min=1, max=10, help="Number of characters to indent on YAML display"),
    ] = 2,
    log_level: LogLevelOption = "info",
) -> None:
    """Create a version of the OpenAPI spec with limited data.

    The data is focused on the operations and paths required for use with the provide layout file.
    """
    def _operations(_node: LayoutNode) -> set[str]:
        ops = {op.identifier for op in _node.operations()}
        for sub in _node.subcommands():
            ops.update(_operations(sub))
        return ops

    init_logging(log_level, GENERATOR_LOG_CLASS)
    layout = layout_tree_with_error_handling(layout_file, start=start)
    oas = open_oas_with_error_handling(openapi_file)
    updated = deepcopy(oas)

    operations = _operations(layout)
    if remove_properties:
        for prop_name in remove_properties:
            updated = remove_property(updated, prop_name)

    updated = schema_operations_filter(updated, allow=operations)
    if remove_all_tags:
        updated = remove_schema_tags(updated)

    if nullable_not_required:
        updated = set_nullable_not_required(updated)

    out_file = updated_file or openapi_file
    with open(out_file, "w", encoding="utf-8", newline="\n") as fp:
        yaml.dump(updated, fp, indent=indent, sort_keys=True)

    typer.echo(f"Wrote to {out_file}")
    return


if __name__ == "__main__":
    app()
