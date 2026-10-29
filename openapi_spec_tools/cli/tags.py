#!/usr/bin/env python3
"""Implement the 'oas analyze tags' CLI commands."""
from typing import Annotated

import typer
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import OasField

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to tags")


@app.command(name="list", short_help="List tags in OpenAPI spec")
def tags_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[str | None, typer.Option("--contains", help="Search for this value in the tag names")] = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    # NOTE: not all OAS's include a "tags" section, so walk the operations

    tags = set()
    for path_data in spec.get(OasField.PATHS, {}).values():
        for method, operation in path_data.items():
            if method == OasField.PARAMS:
                continue

            for t in operation.get(OasField.TAGS):
                tags.add(t)

    names = sorted(tags)
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    console = console_factory()
    match_info = f" matching '{search}'" if search else ""
    if not names:
        console.print(f"No tags found{match_info}")
    else:
        console.print(f"Found {len(names)} tags{match_info}:")
        for n in names:
            console.print(f"{INDENT}{n}")

    return


@app.command(name="show", short_help="Show the tag schema")
def tags_show(
    filename: OpenApiFilenameArgument,
    tag_name: Annotated[str, typer.Argument(help="Name of the tag to show")],
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = {}
    for path, path_data in spec.get(OasField.PATHS, {}).items():
        params = path_data.get(OasField.PARAMS)
        for method, operation in path_data.items():
            if method == OasField.PARAMS:
                continue

            if tag_name in operation.get(OasField.TAGS):
                op_id = operation.get(OasField.OP_ID)
                operation[OasField.X_PATH] = path
                operation[OasField.X_METHOD] = method
                operation[OasField.X_PATH_PARAMS] = params
                operations[op_id] = operation

    if not operations:
        error_out(f"failed to find {tag_name}")

    console = console_factory()
    names = sorted(operations.keys())
    console.print(f"Tag {tag_name} has {len(names)} operations:")
    for n in names:
        console.print(f"{INDENT}{n}")
    return
