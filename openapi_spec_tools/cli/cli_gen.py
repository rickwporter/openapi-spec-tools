#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from copy import deepcopy
from pathlib import Path
from typing import Annotated
from typing import Optional

import typer
import yaml

from openapi_spec_tools.base_gen.files import set_copyright
from openapi_spec_tools.cli._arguments import CopyrightFileOption
from openapi_spec_tools.cli._arguments import LayoutFilenameArgument
from openapi_spec_tools.cli._arguments import LogLevelOption
from openapi_spec_tools.cli._arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli._arguments import StartPointOption
from openapi_spec_tools.cli._utils import console_factory
from openapi_spec_tools.cli._utils import init_logging
from openapi_spec_tools.cli._utils import layout_tree_with_error_handling
from openapi_spec_tools.cli._utils import open_oas_with_error_handling
from openapi_spec_tools.cli_gen._tree import TreeDisplay
from openapi_spec_tools.cli_gen._tree import create_tree_table
from openapi_spec_tools.cli_gen.cli_generator import CliGenerator
from openapi_spec_tools.cli_gen.files import check_for_missing
from openapi_spec_tools.cli_gen.files import copy_infrastructure
from openapi_spec_tools.cli_gen.files import copy_tests
from openapi_spec_tools.cli_gen.files import find_unreferenced
from openapi_spec_tools.cli_gen.files import generate_node
from openapi_spec_tools.cli_gen.files import generate_tree_file
from openapi_spec_tools.cli_gen.files import generate_tree_node
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import DEFAULT_START
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required

SEP = "\n    "
LOG_CLASS = "cli-gen"

#################################################
# Utilities
#################################################
# Top-level stuff
app = typer.Typer(
    no_args_is_help=True,
    help="Various operations for CLI generation."
)


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
    copyright_file: CopyrightFileOption = None,
    include_tests: Annotated[bool, typer.Option("--tests/--no-tests", help="Include tests in generated coode")] = True,
    start: StartPointOption = DEFAULT_START,
    log_level: LogLevelOption = "info",
) -> None:
    """Generate CLI code based on the provided parameters.

    Use either `--project-dir` to set both relative code and test directories, or
    set the paths specifically using `--code-dir` and `--test-dir`.
    """
    logger = init_logging(log_level, LOG_CLASS)

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

    commands = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)

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

    generator = CliGenerator(package_name, oas, logger)
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
    logger = init_logging(log_level, LOG_CLASS)
    commands = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)

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
    logger = init_logging(log_level, LOG_CLASS)
    commands = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)

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
    logger = init_logging(log_level, LOG_CLASS)
    layout = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)
    generator = CliGenerator("", oas, logger)

    tree = generate_tree_node(generator, layout)
    if not tree.children:
        typer.echo("No operations or sub-commands found")
        return

    table = create_tree_table(tree, display, max_depth)
    table.show_header = True
    table.expand = False
    console = console_factory()
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

    logger = init_logging(log_level, LOG_CLASS)
    layout = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)
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
