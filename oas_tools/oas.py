#!/usr/bin/env python3
import sys
from copy import deepcopy
from itertools import zip_longest
from typing import Any
from typing import Optional

import typer
import yaml
from rich import print
from typing_extensions import Annotated

INDENT = "    "

COMPONENTS = "components"
OP_ID = "operationId"
PATHS = "paths"
SCHEMAS = "schemas"
TAGS = "tags"

X_METHOD = "x-method"
X_PATH = "x-path"
X_PATH_PARAMS = "x-path-params"


def open_oas(filename: str) -> Any:
    with open(filename, "r") as fp:
        return yaml.safe_load(fp)


def unroll(full_set: dict[str, set[str]], items: set[str]) -> set[str]:
    """Utility to unroll all the references from items"""
    result = deepcopy(items)

    for i in items:
        sub = full_set.get(i)
        if sub:
            result.update(unroll(full_set, sub))

    return result


def find_dict_prop(obj: dict[str, Any], prop_name: str) -> set[str]:
    result = set()
    for name, data in obj.items():
        if name == prop_name:
            result.add(data)
        elif isinstance(data, list):
            result.update(find_list_prop(data, prop_name))
        elif isinstance(data, dict):
            result.update(find_dict_prop(data, prop_name))

    return result


def find_list_prop(items: list[Any], prop_name: str) -> set[str]:
    result = set()
    for item in items:
        if isinstance(item, dict):
            result.update(find_dict_prop(item, prop_name))

    return result


def shorten_text(text: str, max_len: int = 16) -> str:
    if len(text) >= max_len:
        text = text[:max_len - 3] + "..."
    return text


def find_diffs(lhs: dict[str, Any], rhs: dict[str, Any]) -> dict[str, Any]:
    result = {}
    assert isinstance(lhs, dict) and isinstance(rhs, dict)
    lkeys = set(lhs.keys())
    rkeys = set(rhs.keys())

    added = rkeys - lkeys
    for k in added:
        result[k] = "added"

    removed = lkeys - rkeys
    for k in removed:
        result[k] = "removed"

    common = lkeys & rkeys
    for k in common:
        left = lhs[k]
        right = rhs[k]
        if left is None or right is None:
            # avoids failures due to trying to treat right as dict/list
            if left == right:
                pass
            elif left is None:
                result[k] = "original is None"
            elif right is None:
                result[k] = "updated is None"
        elif isinstance(left, dict):
            # recursive call to find sub-object deltas
            diffs = find_diffs(left, right)
            if diffs:
                result[k] = diffs
        elif isinstance(left, list) and left and isinstance(left[0], dict):
            if len(left) != len(right):
                result[k] = f"different lengths: {len(left)} != {len(right)}"
            elif left and isinstance(left[0], dict):
                for index, (lvalue, rvalue) in enumerate(zip_longest(left, right)):
                    # recursive call to find sub-object deltas
                    vdiff = find_diffs(lvalue, rvalue)
                    if vdiff:
                        item_key = f"{k}[{index}]"
                        result[item_key] = vdiff
            else:
                # simple list items here
                lvalues = set(left)
                rvalues = set(right)
                diffs = lvalues ^ rvalues
                if diffs:
                    result[k] = f"contains {len(diffs)} differences"
        elif left != right:
            result[k] = f"{shorten_text(str(left))} != {shorten_text(str(right))}"

    return result


def find_references(obj: dict[str, Any]) -> set[str]:
    refs = find_dict_prop(obj, "$ref")
    return set([_.split("/")[-1] for _ in refs])


def map_operations(paths: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for path, path_data in paths.items():
        for method, op_data in path_data.items():
            op_id = op_data.get(OP_ID)
            op_data[X_PATH_PARAMS] = path
            op_data[X_METHOD] = method
            result[op_id] = op_data

    return result


def find_paths(paths: dict[str, Any], search: Optional[str] = None, sub_paths: bool = False) -> dict[str, Any]:
    result = {}
    for path, path_data in paths.items():
        if search:
            if not sub_paths and path != search:
                continue
            if sub_paths and path.startswith(search):
                continue
        result[path] = path_data

    return result


#################################################
# CLI stuff
app = typer.Typer(name="oas", no_args_is_help=True, short_help="OpenAPI specification")


OasFilenameArgument = Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification file")]


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
        print(f"[red]ERROR:[/red] failed to find {operation_name}")
        sys.exit(1)

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
        print(f"[red]ERROR:[/red] failed to find {path_name}")
        sys.exit(1)


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
        print(f"[red]ERROR:[/red] failed to find {path_name}")
        sys.exit(1)


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
        print(f"[red]ERROR:[/red] failed to find {model_name}")
        sys.exit(1)

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
        print(f"[red]ERROR:[/red] no model '{model_name}' found")
        sys.exit(1)

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
        print(f"[red]ERROR:[/red] no model '{model_name}' found")
        sys.exit(1)

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
        print(f"[red]ERROR:[/red] failed to find {tag_name}")
        sys.exit(1)

    names = sorted(operations.keys())
    print(f"Tag {tag_name} has {len(names)} operations:")
    for n in names:
        print(f"{INDENT}{n}")
    return



if __name__ == "__main__":
    app()
