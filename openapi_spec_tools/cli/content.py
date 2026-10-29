#!/usr/bin/env python3
"""Implement the 'oas analyze content' CLI commands."""
from typing import Annotated

import typer
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.utils import map_content_types

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to content-types")


@app.command("list", short_help="List operations by response content-type")
def content_type_list(
    filename: OpenApiFilenameArgument,
    max_size: Annotated[int, typer.Option(help="Maximum number of operations to show")] = 10,
    content_type: Annotated[str | None, typer.Option(help="Only display for specified content type")] = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)
    content = map_content_types(spec)

    if content_type:
        content = {k: v for k, v in content.items() if k == content_type}

    console = console_factory()
    if not content:
        console.print("No content-types found")
        return

    for name, operations in content.items():
        console.print(name)
        for op_id in sorted(operations)[:max_size]:
            console.print(f"    {op_id}")
        if len(operations) > max_size:
            console.print("    ...")
            console.print(f"    + {len(operations) - max_size} more")
