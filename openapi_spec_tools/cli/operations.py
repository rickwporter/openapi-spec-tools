#!/usr/bin/env python3
"""Implement the 'oas analyze ops' CLI commands."""
from typing import Annotated

import typer
import yaml
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import ExpansionOption
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import perform_expansion
from openapi_spec_tools.cli.utils import remove_dict_prefix
from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import model_filter

INDENT = "    "

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to operations")

OperationNameArgument = Annotated[str, typer.Argument(metavar="NAME", help="Name of the operation")]
ContentTypeOption = Annotated[
    str | None,
    typer.Option(show_default=False, help="Specific content type to match (otherwise uses first standard type)"),
]


@app.command(name="list", short_help="List operations in OpenAPI spec")
def operation_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[
        str | None,
        typer.Option("--contains", help="Search for this value in the operation names"),
    ] = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    names = sorted(operations.keys())
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    console = console_factory()
    match_info = f" matching '{search}'" if search else ""
    if not names:
        console.print(f"No operations found{match_info}")
    else:
        console.print(f"Found {len(names)} operations{match_info}:")
        for n in names:
            console.print(f"{INDENT}{n}")

    return


@app.command(name="show", short_help="Show the opertions schema")
def operation_show(
    filename: OpenApiFilenameArgument,
    operation_name: OperationNameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    path = operation.pop(OasField.X_PATH)
    path_params = operation.pop(OasField.X_PATH_PARAMS, None)
    method = operation.pop(OasField.X_METHOD)
    inner = {}
    if path_params:
        inner["params"] = path_params
    inner[method] = operation

    console = console_factory()
    console.print(yaml.dump({path: inner}, indent=len(INDENT)))
    return


@app.command(name="models", short_help="List the models referenced by the specified operaton")
def operation_models(
    filename: OpenApiFilenameArgument,
    operation_name: OperationNameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    op_references = find_references(operation)
    models = map_models(spec.get(OasField.COMPONENTS, {}))
    matches = model_filter(models, op_references)

    console = console_factory()
    if not matches:
        console.print(f"{operation_name} does not reference any models")
    else:
        matches = remove_dict_prefix(matches)
        console.print(f"Found {operation_name} uses {len(matches)} models:")
        for n in sorted(matches):
            console.print(f"{INDENT}{n}")

    return


@app.command("parameters", short_help="Display the parameters for the specified operation")
def operations_parameters(
    filename: OpenApiFilenameArgument,
    operation_name: OperationNameArgument,
    expansion: ExpansionOption = "none",
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    # Path-item parameters apply to every operation on the path.
    params = [
        *(operation.get(OasField.X_PATH_PARAMS) or []),
        *(operation.get(OasField.PARAMS) or []),
    ]
    console = console_factory()
    if not params:
        console.print(f"{operation_name} has no parameters")
        return

    components = spec.get(OasField.COMPONENTS, {})
    params = [perform_expansion(expansion, item, components, None) for item in params]

    title = f"Found {operation_name} parameters:"
    text = INDENT + yaml.dump(params, indent=len(INDENT)).replace("\n", "\n" + INDENT)
    console.print(title)
    console.print(text)
    return


@app.command("request", short_help="Display the request body for the specified operation")
def operation_request_body(
    filename: OpenApiFilenameArgument,
    operation_name: OperationNameArgument,
    expansion: ExpansionOption = "none",
    content_type: ContentTypeOption = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    body = operation.get(OasField.REQ_BODY, {})
    content = body.get(OasField.CONTENT)
    if not content:
        error_out(f"no {OasField.REQ_BODY.value} for {operation_name}")

    found = None
    for name, data in content.items():
        if not ContentType.is_value(name) or (content_type and name != content_type):
            continue
        schema = data.get(OasField.SCHEMA)
        if not schema:
            continue
        content_type = name
        found = schema
        break

    if not found:
        content_msg = "standard" if not content_type else content_type
        error_out(f"no {content_msg} content found for {operation_name}")

    components = spec.get(OasField.COMPONENTS, {})
    found = perform_expansion(expansion, found, components, None)

    required = "required " if body.get(OasField.REQUIRED, False) else ""
    title = f"Found {operation_name} {required}request-body ({content_type}):"
    text = INDENT + yaml.dump(found, indent=len(INDENT)).replace("\n", "\n" + INDENT)
    console = console_factory()
    console.print(title)
    console.print(text)
    return


@app.command("response", short_help="Display the response body for the specified operation")
def operation_response_body(
    filename: OpenApiFilenameArgument,
    operation_name: OperationNameArgument,
    expansion: ExpansionOption = "none",
    content_type: ContentTypeOption = None,
    response_code: Annotated[
        str | None,
        typer.Option(
            "--response",
            show_default=False,
            help="Specific response code. Unspecified looks for first 2xx response",
        ),
    ] = None,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    operations = map_operations(spec.get(OasField.PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    responses = operation.get(OasField.RESPONSES)
    if not responses:
        error_out(f"no responses for {operation_name}")

    found_schema = None
    found_code = None
    found_type = None
    for code, resp_data in responses.items():
        unmatched = response_code is not None and response_code != code
        unsuccessful = response_code is None and not code.startswith("2")
        if unmatched or unsuccessful:
            continue

        if resp_data.keys() == {OasField.REFS.value}:
            found_schema = resp_data
            found_code = code
            found_type = ""
            break

        content = resp_data.get(OasField.CONTENT, {})
        for cont_name, cont_data in content.items():
            if not ContentType.is_value(cont_name) or (content_type and cont_name != content_type):
                continue
            schema = cont_data.get(OasField.SCHEMA)
            if not schema:
                continue
            found_code = code
            found_schema = schema
            found_type = f" ({cont_name})"
            break

        if found_code:
            break

    if not found_schema:
        ctype = "standard" if not content_type else content_type
        rtype = "successful" if not response_code else response_code
        error_out(f"no {rtype} {ctype} response found for {operation_name}")

    components = spec.get(OasField.COMPONENTS, {})
    found_schema = perform_expansion(expansion, found_schema, components, None)

    title = f"Found {operation_name} {found_code} response{found_type}:"
    text = INDENT + yaml.dump(found_schema, indent=len(INDENT)).replace("\n", "\n" + INDENT)
    console = console_factory()
    console.print(title)
    console.print(text)
    return
