#!/usr/bin/env python3
"""Implement the 'oas' CLI with options for analyzing and modifying OpenAPI specs."""
from copy import deepcopy
from enum import Enum
from typing import Annotated

import typer
import yaml
from rich_objects import console_factory

from openapi_spec_tools.cli.analyze import app as analyze_app
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.arguments import UpdatedOpenApiFilenameOption
from openapi_spec_tools.cli.history import app as history_app
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import short_filename
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import count_values
from openapi_spec_tools.utils import find_diffs
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required

INDENT = "    "


#################################################
# Top-level stuff
app = typer.Typer(
    name="oas",
    no_args_is_help=True,
    short_help="OpenAPI specification tools",
    help="Various utilities for inspecting, analyzing and modifying OpenAPI specifications.",
)
app.add_typer(history_app, name="history")
app.add_typer(analyze_app, name="analyze")


@app.command("info", short_help="Display the 'info' from the OpenAPI specification")
def info(
    filename: OpenApiFilenameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    info = spec.get("info", {})
    console = console_factory()
    console.print(yaml.dump({"info": info}, indent=len(INDENT)))
    return


@app.command("summary", short_help="Display summary of OAS data")
def summary(
    filename: OpenApiFilenameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)
    method_count = {
        'get': 0,
        'put': 0,
        'patch': 0,
        'delete': 0,
        'post': 0,
    }
    path_count = 0
    model_count = len(map_models(spec.get(OasField.COMPONENTS, {})))
    tag_count = {}

    for path_data in spec.get(OasField.PATHS, {}).values():
        path_count += 1
        for method, operation in path_data.items():
            if method == OasField.PARAMS:
                continue

            method_count[method] += 1
            for tag in operation.get(OasField.TAGS, []):
                orig = tag_count.get(tag, 0)
                tag_count[tag] = orig + 1

    console = console_factory()
    console.print(f"OpenAPI spec ({short_filename(filename)}):")
    console.print(f"{INDENT}Models: {model_count}")
    console.print(f"{INDENT}Paths: {path_count}")
    console.print(f"{INDENT}Operation methods ({sum(method_count.values())}):")
    for k, v in method_count.items():
        console.print(f"{INDENT * 2}{k}: {v}")
    console.print(f"{INDENT}Tags ({len(tag_count)}) with operation counts:")
    for k, v in tag_count.items():
        console.print(f"{INDENT * 2}{k}: {v}")

    return


@app.command("diff", short_help="Compare two OAS files")
def diff(
    original: Annotated[
        str,
        typer.Argument(metavar="FILENAME", show_default=False, help="Original OpenAPI specification filename"),
    ],
    updated: Annotated[
        str,
        typer.Argument(metavar="FILENAME", show_default=False, help="Updated OpenAPI specification filename"),
    ],
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    old_spec = open_oas_with_error_handling(original, logger)
    new_spec = open_oas_with_error_handling(updated, logger)

    console = console_factory()
    diffs = find_diffs(old_spec, new_spec)
    if not diffs:
        console.print(f"No differences between {short_filename(original)} and {short_filename(updated)}")
    else:
        console.print(yaml.dump(diffs, indent=len(INDENT)))
    return


class DisplayOption(str, Enum):
    """Options for displaying the output."""

    NONE = "none"
    SUMMARY = "summary"
    DIFF = "diff"
    FINAL = "final"


@app.command("update", short_help="Update the OpenAPI spec")
def update(
    original_filename: OpenApiFilenameArgument,
    updated_filename: UpdatedOpenApiFilenameOption = None,
    nullable_not_required: Annotated[
        bool,
        typer.Option(help="Remove 'nullable' properties from required list"),
    ] = False,
    remove_all_tags: Annotated[bool, typer.Option(help="Remove all tags")] = False,
    remove_operations: Annotated[
        list[str] | None,
        typer.Option("--remove-op", show_default=False, help="List of operations to remove"),
    ] = None,
    allowed_operations: Annotated[
        list[str] | None,
        typer.Option("--allow-op", show_default=False, help="List of operations to keep"),
    ] = None,
    remove_properties: Annotated[
        list[str] | None,
        typer.Option("--remove", show_default=False, help="List of properties to remove."),
    ] = None,
    display_option: Annotated[
        DisplayOption,
        typer.Option("--display", help="Shown on console at conclusion", case_sensitive=False),
    ] = DisplayOption.DIFF,
    indent: Annotated[
        int,
        typer.Option(min=1, max=10, help="Number of characters to indent on YAML display"),
    ] = len(INDENT),
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    old_spec = open_oas_with_error_handling(original_filename, logger)
    updated = deepcopy(old_spec)

    if allowed_operations and remove_operations:
        error_out("cannot specify both --allow-op and --remove-op")

    if remove_all_tags:
        updated = remove_schema_tags(updated)

    if remove_properties:
        for prop_name in remove_properties:
            updated = remove_property(updated, prop_name)

    if nullable_not_required:
        updated = set_nullable_not_required(updated)

    if remove_operations:
        updated = schema_operations_filter(updated, remove=set(remove_operations))

    if allowed_operations:
        updated = schema_operations_filter(updated, allow=set(allowed_operations))

    if updated_filename:
        with open(updated_filename, "w", encoding="utf-8", newline="\n") as fp:
            yaml.dump(updated, fp, indent=indent)

    console = console_factory()
    diffs = find_diffs(old_spec, updated)
    if display_option == DisplayOption.NONE:
        pass
    elif display_option == DisplayOption.FINAL:
        console.print(yaml.dump(updated, indent=indent))
    elif not diffs:
        console.print(f"No differences between {short_filename(original_filename)} and updated")
    elif display_option == DisplayOption.DIFF:
        console.print(yaml.dump(diffs, indent=indent))
    else:  # must be DisplayOption.SUMMARY:
        diff_count = count_values(diffs)
        console.print(f"Found {diff_count} differences from {short_filename(original_filename)}")

    return


if __name__ == "__main__":
    app()
