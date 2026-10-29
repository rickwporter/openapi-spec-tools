#!/usr/bin/env python3
"""Implement the 'oas analyze models' CLI commands."""
from typing import Annotated

import typer
import yaml
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import ExpansionOption
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import perform_expansion
from openapi_spec_tools.cli.utils import remove_dict_prefix
from openapi_spec_tools.cli.utils import remove_list_prefix
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import model_filter
from openapi_spec_tools.utils import model_full_name
from openapi_spec_tools.utils import model_references
from openapi_spec_tools.utils import models_referenced_by
from openapi_spec_tools.utils import unroll

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to models")

ModelNameArgument = Annotated[str, typer.Argument(metavar="NAME", help="Name of the model")]


@app.command(name="list", short_help="List models in OpenAPI spec")
def models_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[
        str | None,
        typer.Option("--contains", help="Search for this value in the model names"),
    ] = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    models = map_models(spec.get(OasField.COMPONENTS, {}))
    names = sorted(models.keys())
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    console = console_factory()
    match_info = f" matching '{search}'" if search else ""
    if not names:
        console.print(f"No models found{match_info}")
    else:
        console.print(f"Found {len(names)} models{match_info}:")
        names = remove_list_prefix(names)
        for n in names:
            console.print(f"{INDENT}{n}")

    return


@app.command(name="show", short_help="Show the model schema")
def models_show(
    filename: OpenApiFilenameArgument,
    model_name: ModelNameArgument,
    include_referenced: Annotated[bool, typer.Option("--references", help="Include referenced models")] = False,
    expansion: ExpansionOption = "none",
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    components = spec.get(OasField.COMPONENTS, {})
    models = map_models(components)
    full_name = model_full_name(models, model_name)
    model = models.get(full_name)
    if not model:
        error_out(f"failed to find {model_name}")

    if not include_referenced:
        models = {full_name: model}
    else:
        models = model_filter(models, {full_name})

    models = {name: perform_expansion(expansion, schema, components, name) for name, schema in models.items()}

    models = remove_dict_prefix(models)
    console = console_factory()
    console.print(yaml.dump(models, indent=len(INDENT)))
    return


@app.command(name="uses", short_help="List sub-models used by the specified model")
def models_uses(
    filename: OpenApiFilenameArgument,
    model_name: ModelNameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    models = map_models(spec.get(OasField.COMPONENTS, {}))
    full_name = model_full_name(models, model_name)
    if not full_name:
        error_out(f"no model '{model_name}' found")

    references = model_references(models)

    console = console_factory()
    matches = unroll(references, references.get(full_name))
    if not matches:
        console.print(f"{model_name} does not use any other models")
    else:
        matches = remove_list_prefix(list(matches))
        console.print(f"Found {model_name} uses {len(matches)} models:")
        for n in sorted(matches):
            console.print(f"{INDENT}{n}")

    return


@app.command(name="used-by", short_help="List models which reference the specified model")
def models_used_by(
    filename: OpenApiFilenameArgument,
    model_name: ModelNameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    models = map_models(spec.get(OasField.COMPONENTS, {}))
    full_name = model_full_name(models, model_name)
    if not full_name:
        error_out(f"no model '{model_name}' found")

    console = console_factory()
    matches = models_referenced_by(models, full_name)
    if not matches:
        console.print(f"{model_name} is not used by any other models")
    else:
        matches = remove_list_prefix(list(matches))
        console.print(f"Found {model_name} is used by {len(matches)} models:")
        for n in sorted(matches):
            console.print(f"{INDENT}{n}")

    return


@app.command(name="ops", short_help="List operations which reference the specified model")
def models_operations(
    filename: OpenApiFilenameArgument,
    model_name: ModelNameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    models = map_models(spec.get(OasField.COMPONENTS, {}))
    full_name = model_full_name(models, model_name)
    if not full_name:
        error_out(f"no model '{model_name}' found")

    model_refs = models_referenced_by(models, full_name)
    model_refs.add(full_name)  # include the direct references, too

    matches = []
    for path_data in spec.get(OasField.PATHS, {}).values():
        for method, op_data in path_data.items():
            if method == OasField.PARAMS:
                continue
            references = find_references(op_data)
            if references.intersection(model_refs):
                op_id = op_data.get(OasField.OP_ID)
                matches.append(op_id)

    matches = remove_list_prefix(matches)
    console = console_factory()
    console.print(f"Found {model_name} is used by {len(matches)} operations:")
    for n in sorted(matches):
        console.print(f"{INDENT}{n}")

    return
