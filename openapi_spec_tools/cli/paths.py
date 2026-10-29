#!/usr/bin/env python3
"""Implement the 'oas analyze paths' CLI commands."""
from typing import Annotated

import typer
import yaml
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import find_paths
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import model_filter
from openapi_spec_tools.utils import unmap_models

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to paths")

PathSearchOption = Annotated[str | None, typer.Option("--contains", help="Search for this value in the path")]
PathSubpathOption = Annotated[
    bool,
    typer.Option("--sub-paths", help="Include sub-paths of the search value"),
]
PathModelsOption = Annotated[bool, typer.Option("--models", help="Include the referenced models")]

@app.command(name="list", short_help="List paths in OpenAPI spec")
def paths_list(
    filename: OpenApiFilenameArgument,
    search: PathSearchOption = None,
    include_subpaths: PathSubpathOption = False,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    paths = find_paths(spec.get(OasField.PATHS, {}), search, include_subpaths)
    names = sorted(paths.keys())

    match_info = ""
    if search:
        match_info = f" matching '{search}'"
        if include_subpaths:
            match_info += " including sub-paths"

    console = console_factory()
    if not names:
        console.print(f"No paths found{match_info}")
    else:
        console.print(f"Found {len(names)} paths{match_info}:")
        for n in names:
            console.print(f"{INDENT}{n}")

    return


@app.command(name="show", short_help="Show the path schema")
def paths_show(
    filename: OpenApiFilenameArgument,
    path_name: Annotated[str, typer.Argument(help="Name of the path to show")],
    include_subpaths: PathSubpathOption = False,
    include_models: PathModelsOption = False,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    paths = find_paths(spec.get(OasField.PATHS, {}), path_name, include_subpaths)
    if not paths:
        error_out(f"failed to find {path_name}")

    if include_models:
        references = find_references(paths)
        models = map_models(spec.get(OasField.COMPONENTS, {}))
        used = model_filter(models, references)
        results = {
            OasField.PATHS.value: paths,
            OasField.COMPONENTS.value: unmap_models(used),
        }
        paths = results

    console = console_factory()
    console.print(yaml.dump(paths, indent=len(INDENT)))
    return



@app.command(name="ops", short_help="Show the operations in the specified path")
def paths_operations(
    filename: OpenApiFilenameArgument,
    path_name: Annotated[str, typer.Option(help="Name of the path to show")],
    include_subpaths: PathSubpathOption = False,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    result = {}
    paths = find_paths(spec.get(OasField.PATHS, {}), path_name, include_subpaths)
    for path, path_data in paths.items():
        for method, op_data in path_data.items():
            if method == OasField.PARAMS:
                continue
            op_id = op_data.get(OasField.OP_ID)
            items = result.get(path, []) + [op_id]
            result[path] = items

    if not result:
        error_out(f"failed to find {path_name}")

    console = console_factory()
    console.print(yaml.dump(result, indent=len(INDENT)))
    return
