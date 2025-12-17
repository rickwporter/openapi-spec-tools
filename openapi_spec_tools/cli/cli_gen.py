#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from copy import deepcopy
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Optional

import typer
import yaml
from rich_objects import console_factory

from openapi_spec_tools.base_gen.files import set_copyright
from openapi_spec_tools.cli.arguments import CodeDirectoryOption
from openapi_spec_tools.cli.arguments import CopyrightFileOption
from openapi_spec_tools.cli.arguments import IndentOption
from openapi_spec_tools.cli.arguments import LayoutFilenameArgument
from openapi_spec_tools.cli.arguments import LayoutFilenameOption
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.arguments import PackageNameArgument
from openapi_spec_tools.cli.arguments import PathPrefixOption
from openapi_spec_tools.cli.arguments import StartPointOption
from openapi_spec_tools.cli.arguments import UpdatedOpenApiFilenameOption
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import layout_tree_with_error_handling
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import write_layout_tree
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
from openapi_spec_tools.layout.layout_generator import LayoutGenerator
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import DEFAULT_START
from openapi_spec_tools.layout.utils import path_to_parts
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required

SEP = "\n    "
LOG_CLASS = "cli-gen"
FILENAME = "FILENAME"
DIRECTORY = "DIRECTORY"

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
    openapi_file: OpenApiFilenameArgument,
    package_name: PackageNameArgument,
    layout_file: LayoutFilenameOption = None,
    project_dir: Annotated[
        Optional[str],
        typer.Option(metavar=DIRECTORY, show_default=False, help="Project directory name")
    ] = None,
    code_dir: CodeDirectoryOption = None,
    test_dir: Annotated[
        Optional[str],
        typer.Option(metavar=DIRECTORY, show_default=False, help="Directory for tests -- overrides default")
    ] = None,
    copyright_file: CopyrightFileOption = None,
    include_tests: Annotated[bool, typer.Option("--tests/--no-tests", help="Include tests in generated coode")] = True,
    prefix: PathPrefixOption = "",
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

    if copyright_file:
        text = Path(copyright_file).read_text()
        set_copyright(text)

    oas = open_oas_with_error_handling(openapi_file, logger)
    if layout_file:
        commands = layout_tree_with_error_handling(layout_file, start, logger)

        missing = check_for_missing(commands, oas)
        if missing:
            typer.echo(render_missing(missing))
            raise typer.Exit(1)
    else:
        layout_gen = LayoutGenerator(oas)
        commands = layout_gen.generate(prefix)
        typer.echo("Generated layout -- equivalent can be saved using 'layout suggest'.")

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


def find_parent(
    node: LayoutNode,
    operations: dict[str, Any],
    path_parts: list[str],
    prefix: str,
) -> Optional[LayoutNode]:
    """Find the parent node (if any) where an operation matches the path parts.

    The LayoutNode's only know the operationId (not the path), so the operations are needed to
    retrieve the path parts.
    """
    for node_op in node.operations():
        operation = operations.get(node_op.identifier) or {}
        node_parts = path_to_parts(operation.get(OasField.X_PATH, ""), prefix)
        if path_parts == node_parts:
            return node

    for child in node.subcommands():
        node_op = find_parent(child, operations, path_parts, prefix)
        if node_op:
            return node_op

    return None


@app.command("update", help="Updates the layout file with the missing operations.")
def update_layout(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    new_file: Annotated[
        Optional[str],
        typer.Option(metavar="FILENAME", help="New filename (if different than original)")
    ] = None,
    start: StartPointOption = DEFAULT_START,
    prefix: PathPrefixOption = "",
    indent: IndentOption = 4,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    commands = layout_tree_with_error_handling(layout_file, start=start, logger=logger)
    oas = open_oas_with_error_handling(openapi_file, logger)

    unreferenced = find_unreferenced(commands, oas)
    if not unreferenced:
        typer.echo("No unreferenced operations found")
        return

    generator = LayoutGenerator(oas)
    operations = map_operations(oas.get(OasField.PATHS))

    # walk the list of unreference operations, and try to fit them in
    for op_id, unref in unreferenced.items():
        parts = path_to_parts(unref.get(OasField.X_PATH), prefix)
        command = generator.suggest_command(unref)
        pagination = generator.get_pagination(unref)
        op_node = LayoutNode(command=command, identifier=op_id, pagination=pagination)

        # attempt to find parent based on path
        parent = find_parent(commands, operations, parts, prefix)
        if parent:
            logger.debug(f"Found parent for {op_id}")
        else:
            logger.debug(f"Created node path for {op_id}")
            parent = generator.get_or_create_node_with_parents(commands, parts)

        parent.children.append(op_node)

    write_layout_tree(new_file or layout_file, commands, logger, indent)
    typer.echo(f"\nAdded {len(unreferenced)} operations")


@app.command("tree", help="Displays the CLI tree")
def show_cli_tree(
    layout_file: LayoutFilenameArgument,
    openapi_file: OpenApiFilenameArgument,
    start: StartPointOption = DEFAULT_START,
    display: Annotated[
        TreeDisplay,
        typer.Option(case_sensitive=False, help="Details to show about tree")
    ] = TreeDisplay.ALL,
    max_depth: Annotated[int, typer.Option(metavar="DEPTH", help="Maximum tree depth to show")] = 10,
    search: Annotated[
        Optional[str],
        typer.Option(metavar="NEEDLE", help="Only show the tree for items with this needle.")
    ] = None,
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

    table = create_tree_table(tree, display, max_depth, search)
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
    updated_file: UpdatedOpenApiFilenameOption = None,
    remove_properties: Annotated[
        Optional[list[str]],
        typer.Option("--remove", metavar="PROPERTIES", show_default=False, help="List of properties to remove."),
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
