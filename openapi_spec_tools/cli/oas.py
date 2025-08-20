#!/usr/bin/env python3
"""Implement the 'oas' CLI with options for analyzing and modifying OpenAPI specs."""
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Optional

import typer
import yaml

from openapi_spec_tools.cli._arguments import LogLevelOption
from openapi_spec_tools.cli._arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli._utils import console_factory
from openapi_spec_tools.cli._utils import error_out
from openapi_spec_tools.cli._utils import init_logging
from openapi_spec_tools.cli._utils import open_oas_with_error_handling
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import count_values
from openapi_spec_tools.utils import find_diffs
from openapi_spec_tools.utils import find_paths
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import map_content_types
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import model_filter
from openapi_spec_tools.utils import model_full_name
from openapi_spec_tools.utils import model_references
from openapi_spec_tools.utils import models_referenced_by
from openapi_spec_tools.utils import remove_property
from openapi_spec_tools.utils import remove_schema_tags
from openapi_spec_tools.utils import schema_operations_filter
from openapi_spec_tools.utils import set_nullable_not_required
from openapi_spec_tools.utils import unmap_models
from openapi_spec_tools.utils import unroll

INDENT = "    "
LOG_CLASS = "oas"


def short_filename(long: str) -> str:
    """Shorten the filename to just the name portion."""
    return Path(long).name


def remove_list_prefix(items: list[str]) -> list[str]:
    """Remove a common model prefix. This typically happens when everything is in schemas/."""
    prefix = items[0].split('/')[0] + '/'
    if not all(_.startswith(prefix) for _ in items):
        return items

    return [_.replace(prefix, "") for _ in items]


def remove_dict_prefix(map: dict[str, Any]) -> dict[str, Any]:
    """Remove common prefix segements (delineated by /'s) from dictionary keys.

    If all the keys of the provided map start with the same prefix (before /), it removes the prefix from the keys.
    """
    keys = list(map.keys())
    prefix = keys[0].split('/')[0] + '/'
    if not all(_.startswith(prefix) for _ in keys):
        return map

    return {k.replace(prefix, ""): v for k, v in map.items()}


#################################################
# Top-level stuff
app = typer.Typer(
    name="oas",
    no_args_is_help=True,
    short_help="OpenAPI specification tools",
    help="Various utilities for inspecting, analyzing and modifying OpenAPI specifications.",
)


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
    updated_filename: Annotated[Optional[str], typer.Option(help="Filename for update OpenAPI spec")] = None,
    nullable_not_required: Annotated[
        bool,
        typer.Option(help="Remove 'nullable' properties from required list"),
    ] = False,
    remove_all_tags: Annotated[bool, typer.Option(help="Remove all tags")] = False,
    remove_operations: Annotated[
        Optional[list[str]],
        typer.Option("--remove-op", show_default=False, help="List of operations to remove"),
    ] = None,
    allowed_operations: Annotated[
        Optional[list[str]],
        typer.Option("--allow-op", show_default=False, help="List of operations to keep"),
    ] = None,
    remove_properties: Annotated[
        Optional[list[str]],
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


##########################################
# Analyze
analyze_typer = typer.Typer(no_args_is_help=True, short_help="Tools for analyzing an OAS file")
app.add_typer(analyze_typer, name="analyze")


##########################################
# Operations
op_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to operations")
analyze_typer.add_typer(op_typer, name="ops")


@op_typer.command(name="list", short_help="List operations in OpenAPI spec")
def operation_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[
        Optional[str],
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


@op_typer.command(name="show", short_help="Show the opertions schema")
def operation_show(
    filename: OpenApiFilenameArgument,
    operation_name: Annotated[str, typer.Argument(help="Name of the operation to show")],
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


@op_typer.command(name="models", short_help="List the models referenced by the specified operaton")
def operation_models(
    filename: OpenApiFilenameArgument,
    operation_name: Annotated[str, typer.Argument(help="Name of the operation")],
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


##########################################
# Paths
path_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to paths")
analyze_typer.add_typer(path_typer, name="paths")

PathSearchOption = Annotated[Optional[str], typer.Option("--contains", help="Search for this value in the path")]
PathSubpathOption = Annotated[
    bool,
    typer.Option("--sub-paths", help="Include sub-paths of the search value"),
]
PathModelsOption = Annotated[bool, typer.Option("--models", help="Include the referenced models")]

@path_typer.command(name="list", short_help="List paths in OpenAPI spec")
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


@path_typer.command(name="show", short_help="Show the path schema")
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



@path_typer.command(name="ops", short_help="Show the operations in the specified path")
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


##########################################
# Models
models_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to models")
analyze_typer.add_typer(models_typer, name="models")

@models_typer.command(name="list", short_help="List models in OpenAPI spec")
def models_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[
        Optional[str],
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


@models_typer.command(name="show", short_help="Show the model schema")
def models_show(
    filename: OpenApiFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
    include_referenced: Annotated[bool, typer.Option("--references", help="Include referenced models")] = False,
    log_level: LogLevelOption = "info",
) -> None:
    logger = init_logging(log_level, LOG_CLASS)
    spec = open_oas_with_error_handling(filename, logger)

    models = map_models(spec.get(OasField.COMPONENTS, {}))
    full_name = model_full_name(models, model_name)
    model = models.get(full_name)
    if not model:
        error_out(f"failed to find {model_name}")

    if not include_referenced:
        models = {full_name: model}
    else:
        models = model_filter(models, {full_name})
    models = remove_dict_prefix(models)

    console = console_factory()
    console.print(yaml.dump(models, indent=len(INDENT)))
    return


@models_typer.command(name="uses", short_help="List sub-models used by the specified model")
def models_uses(
    filename: OpenApiFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
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


@models_typer.command(name="used-by", short_help="List models which reference the specified model")
def models_used_by(
    filename: OpenApiFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
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


@models_typer.command(name="ops", short_help="List operations which reference the specified model")
def models_operations(
    filename: OpenApiFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to search for")],
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


##########################################
# Tags
tag_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to tags")
analyze_typer.add_typer(tag_typer, name="tags")

@tag_typer.command(name="list", short_help="List tags in OpenAPI spec")
def tags_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[Optional[str], typer.Option("--contains", help="Search for this value in the tag names")] = None,
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


@tag_typer.command(name="show", short_help="Show the tag schema")
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


##########################################
# Content-type
content_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to content-types")
analyze_typer.add_typer(content_typer, name="content")

@content_typer.command("list", short_help="List operations by response content-type")
def content_type_list(
    filename: OpenApiFilenameArgument,
    max_size: Annotated[int, typer.Option(help="Maximum number of operations to show")] = 10,
    content_type: Annotated[Optional[str], typer.Option(help="Only display for specified content type")] = None,
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


if __name__ == "__main__":
    app()
