#!/usr/bin/env python3
from copy import deepcopy
from enum import Enum
from typing import Optional

import typer
import yaml
from rich import print
from typing_extensions import Annotated

from oas_tools._typer import OasFilenameArgument
from oas_tools._typer import error_out
from oas_tools.constants import COMPONENTS
from oas_tools.constants import OP_ID
from oas_tools.constants import PATHS
from oas_tools.constants import SCHEMAS
from oas_tools.constants import TAGS
from oas_tools.constants import X_METHOD
from oas_tools.constants import X_PATH
from oas_tools.constants import X_PATH_PARAMS
from oas_tools.utils import count_values
from oas_tools.utils import find_diffs
from oas_tools.utils import find_paths
from oas_tools.utils import find_references
from oas_tools.utils import map_operations
from oas_tools.utils import open_oas
from oas_tools.utils import remove_schema_tags
from oas_tools.utils import schema_operations
from oas_tools.utils import set_nullable_not_required
from oas_tools.utils import unroll

INDENT = "    "


#################################################
# CLI stuff
app = typer.Typer(name="oas", no_args_is_help=True, short_help="OpenAPI specification")


@app.command("info", short_help="Display the 'info' from the OpenAPI specification")
def info(
    filename: OasFilenameArgument,
) -> None:
    spec = open_oas(filename)

    info = spec.get("info", {})
    print(yaml.dump({"info": info}, indent=len(INDENT)))
    return


@app.command("summary", short_help="Display suummary of OAS data")
def summary(
    filename: OasFilenameArgument,
) -> None:
    spec = open_oas(filename)
    method_count = {
        'get': 0,
        'put': 0,
        'patch': 0,
        'delete': 0,
        'post': 0,
    }
    path_count = 0
    model_count = len(spec.get(COMPONENTS, {}).get(SCHEMAS, {}))
    tag_count = {}

    for path_data in spec.get(PATHS, {}).values():
        path_count += 1
        for method, operation in path_data.items():
            method_count[method] += 1
            for tag in operation.get(TAGS):
                orig = tag_count.get(tag, 0)
                tag_count[tag] = orig + 1

    print(f"OpenAPI spec ({filename}):")
    print(f"{INDENT}Models: {model_count}")
    print(f"{INDENT}Paths: {path_count}")
    print(f"{INDENT}Operation methods ({sum(method_count.values())}):")
    for k, v in method_count.items():
        print(f"{INDENT * 2}{k}: {v}")
    print(f"{INDENT}Tags ({len(tag_count)}):")
    for k, v in tag_count.items():
        print(f"{INDENT * 2}{k}: {v}")

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
) -> None:
    old_spec = open_oas(original)
    new_spec = open_oas(updated)

    diffs = find_diffs(old_spec, new_spec)
    if not diffs:
        print(f"No differences between {original} and {updated}")
    else:
        print(yaml.dump(diffs, indent=len(INDENT)))
    return


class DisplayOption(str, Enum):
    NONE = "none"
    SUMMARY = "summary"
    DIFF = "diff"
    FINAL = "final"


@app.command("update", short_help="Update the OpenAPI spec")
def update(
    original_filename: OasFilenameArgument,
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
    display_option: Annotated[
        DisplayOption,
        typer.Option("--display", help="Shown on console at conclusion", case_sensitive=False),
    ] = DisplayOption.DIFF,
    indent: Annotated[
        int,
        typer.Option(min=1, max=10, help="Number of characters to indent on YAML display"),
    ] = len(INDENT),
) -> None:
    old_spec = open_oas(original_filename)
    updated = deepcopy(old_spec)

    if allowed_operations and remove_operations:
        error_out("cannot specify both --allow-op and --remove-op")

    if remove_all_tags:
        updated = remove_schema_tags(updated)

    if nullable_not_required:
        updated = set_nullable_not_required(updated)

    if remove_operations:
        updated = schema_operations(updated, remove_ops=set(remove_operations))

    if allowed_operations:
        updated = schema_operations(updated, allow_ops=set(allowed_operations))

    if updated_filename:
        with open(updated_filename, "w") as fp:
            yaml.dump(updated, fp, indent=indent)

    diffs = find_diffs(old_spec, updated)
    if display_option == DisplayOption.NONE:
        pass
    elif display_option == DisplayOption.FINAL:
        print(yaml.dump(updated, indent=indent))
    elif not diffs:
        print(f"No differences between {original_filename} and updated")
    elif display_option == DisplayOption.DIFF:
        print(yaml.dump(diffs, indent=indent))
    elif display_option == DisplayOption.SUMMARY:
        diff_count = count_values(diffs)
        print(f"Found {diff_count} differences from {original_filename}")
    else:
        print(f"Unhandled disply option: {display_option}")

    return


##########################################
# Operations
op_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to operations")
app.add_typer(op_typer, name="ops")


@op_typer.command(name="list", short_help="List models in OpenAPI spec")
def op_list(
    filename: OasFilenameArgument,
    search: Annotated[
        Optional[str],
        typer.Option("--contains", help="Search for this value in the operation names"),
    ] = None,
) -> None:
    spec = open_oas(filename)

    operations = map_operations(spec.get(PATHS, {}))
    names = sorted(operations.keys())
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    match_info = f" matching '{search}'" if search else ""
    if not names:
        print(f"No operations found{match_info}")
    else:
        print(f"Found {len(names)} operations{match_info}")
        for n in names:
            print(f"{INDENT}{n}")

    return


@op_typer.command(name="show", short_help="Show the opertions schema")
def operation_show(
    filename: OasFilenameArgument,
    operation_name: Annotated[str, typer.Argument(help="Name of the model to show")],
) -> None:
    spec = open_oas(filename)

    operations = map_operations(spec.get(PATHS, {}))
    operation = operations.get(operation_name)
    if not operation:
        error_out(f"failed to find {operation_name}")

    path = operation.pop(X_PATH)
    path_params = operation.pop(X_PATH_PARAMS, None)
    method = operation.pop(X_METHOD)
    inner = {}
    if path_params:
        inner["params"] = path_params
    inner[method] = operation

    print(yaml.dump({path: inner}, indent=len(INDENT)))
    return



##########################################
# Paths
path_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to paths")
app.add_typer(path_typer, name="paths")

PathSearchOption = Annotated[Optional[str], typer.Option("--contains", help="Search for this value in the path")]
PathSubpathObtion = Annotated[
    bool,
    typer.Option("--sub-paths/--no-sub-paths", help="Include sub-paths of the search value"),
]

@path_typer.command(name="list", short_help="List paths in OpenAPI spec")
def paths_list(
    filename: OasFilenameArgument,
    search: PathSearchOption = None,
    include_subpaths: PathSubpathObtion = False,
) -> None:
    spec = open_oas(filename)

    paths = find_paths(spec.get(PATHS, {}), search, include_subpaths)
    names = sorted(paths.keys())

    match_info = ""
    if search:
        match_info = f" matching '{search}'"
        if include_subpaths:
            match_info += " including sub-paths"

    if not names:
        print(f"No paths found{match_info}")
    else:
        print(f"Found {len(names)} paths{match_info}")
        for n in names:
            print(f"{INDENT}{n}")

    return


@path_typer.command(name="show", short_help="Show the path schema")
def path_show(
    filename: OasFilenameArgument,
    path_name: Annotated[str, typer.Argument(help="Name of the path to show")],
    include_subpaths: PathSubpathObtion = False,
) -> None:
    spec = open_oas(filename)

    paths = find_paths(spec.get(PATHS, {}), path_name, include_subpaths)
    if not paths:
        error_out(f"failed to find {path_name}")

    print(yaml.dump(paths, indent=len(INDENT)))
    return



@path_typer.command(name="ops", short_help="Show the operations in the specified path")
def path_operations(
    filename: OasFilenameArgument,
    path_name: Annotated[str, typer.Option(help="Name of the path to show")],
    include_subpaths: PathSubpathObtion = False,
) -> None:
    spec = open_oas(filename)

    result = {}
    paths = find_paths(spec.get(PATHS, {}), path_name, include_subpaths)
    for path, path_data in paths.items():
        for op_data in path_data.values():
            op_id = op_data.get(OP_ID)
            if not op_id:
                continue
        items = result.get(path, []) + op_id
        result[path] = items

    if not result:
        error_out(f"failed to find {path_name}")

    print(yaml.dump(result, indent=len(INDENT)))
    return


##########################################
# Models
model_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to models")
app.add_typer(model_typer, name="models")

@model_typer.command(name="list", short_help="List models in OpenAPI spec")
def model_list(
    filename: OasFilenameArgument,
    search: Annotated[
        Optional[str],
        typer.Option("--contains", help="Search for this value in the model names"),
    ] = None,
) -> None:
    spec = open_oas(filename)

    names = sorted(spec.get(COMPONENTS, {}).get(SCHEMAS, {}).keys())
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    match_info = f" matching '{search}'" if search else ""
    if not names:
        print(f"No models found{match_info}")
    else:
        print(f"Found {len(names)} models{match_info}")
        for n in names:
            print(f"{INDENT}{n}")

    return


@model_typer.command(name="show", short_help="Show the model schema")
def model_show(
    filename: OasFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
) -> None:
    spec = open_oas(filename)

    model = spec.get(COMPONENTS, {}).get(SCHEMAS, {}).get(model_name)
    if not model:
        error_out(f"failed to find {model_name}")

    print(yaml.dump({model_name: model}, indent=len(INDENT)))
    return


@model_typer.command(name="uses", short_help="List sub-models used by the specified model")
def model_uses(
    filename: OasFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
) -> None:
    spec = open_oas(filename)

    models = spec.get(COMPONENTS, {}).get(SCHEMAS, {})
    if model_name not in models:
        error_out(f"no model '{model_name}' found")

    references = {
        name: find_references(body)
        for name, body in models.items()
    }

    matches = unroll(references, references.get(model_name))
    print(f"Found {model_name} uses {len(matches)} models:")
    for n in sorted(matches):
        print(f"{INDENT}{n}")

    return


@model_typer.command(name="used-by", short_help="List models which reference the specified model")
def model_used_by(
    filename: OasFilenameArgument,
    model_name: Annotated[str, typer.Argument(help="Name of the model to show")],
) -> None:
    spec = open_oas(filename)

    models = spec.get(COMPONENTS, {}).get(SCHEMAS, {})
    if model_name not in models:
        error_out(f"no model '{model_name}' found")

    referenced = {}
    for name, body in models.items():
        refs = find_references(body)
        for r in refs:
            curr = referenced.get(r, set())
            curr.add(name)
            referenced[r] = curr

    matches = unroll(referenced, referenced.get(model_name))
    print(f"Found {model_name} uses {len(matches)} models:")
    for n in sorted(matches):
        print(f"{INDENT}{n}")

    return


##########################################
# Tags
tag_typer = typer.Typer(no_args_is_help=True, short_help="Inspect things related to tags")
app.add_typer(tag_typer, name="tags")

@tag_typer.command(name="list", short_help="List tags in OpenAPI spec")
def tag_list(
    filename: OasFilenameArgument,
    search: Annotated[Optional[str], typer.Option("--contains", help="Search for this value in the tag names")] = None,
) -> None:
    spec = open_oas(filename)

    # NOTE: not all OAS's include a "tags" section, so walk the operations

    tags = set()
    for path_data in spec.get(PATHS, {}).values():
        for operation in path_data.values():
            for t in operation.get(TAGS):
                tags.add(t)

    names = sorted(tags)
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    match_info = f" matching '{search}'" if search else ""
    if not names:
        print(f"No tags found{match_info}")
    else:
        print(f"Found {len(names)} tags{match_info}")
        for n in names:
            print(f"{INDENT}{n}")

    return


@tag_typer.command(name="show", short_help="Show the tag schema")
def tag_show(
    filename: OasFilenameArgument,
    tag_name: Annotated[str, typer.Argument(help="Name of the tag to show")],
) -> None:
    spec = open_oas(filename)

    operations = {}
    for path, path_data in spec.get(PATHS, {}).items():
        for method, operation in path_data.items():
            if tag_name in operation.get(TAGS):
                op_id = operation.get(OP_ID)
                operation[X_PATH] = path
                operation[X_METHOD] = method
                operations[op_id] = operation

    if not operations:
        error_out(f"failed to find {tag_name}")

    names = sorted(operations.keys())
    print(f"Tag {tag_name} has {len(names)} operations:")
    for n in names:
        print(f"{INDENT}{n}")
    return



if __name__ == "__main__":
    app()
