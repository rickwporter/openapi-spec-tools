from copy import deepcopy
from itertools import zip_longest
from typing import Any
from typing import Optional

import yaml

from oas_tools.constants import COMPONENTS
from oas_tools.constants import NAME
from oas_tools.constants import NULLABLE
from oas_tools.constants import OP_ID
from oas_tools.constants import PARAMS
from oas_tools.constants import PATHS
from oas_tools.constants import PROPS
from oas_tools.constants import REFS
from oas_tools.constants import REQUIRED
from oas_tools.constants import SCHEMAS
from oas_tools.constants import TAGS
from oas_tools.constants import X_METHOD
from oas_tools.constants import X_PATH
from oas_tools.constants import X_PATH_PARAMS


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
        elif isinstance(left, list) and left:
            lvalues = set(left)
            rvalues = set(right)
            deltas = []
            added = rvalues - lvalues
            if added:
                deltas.append(f"added {', '.join(added)}")
            removed = lvalues - rvalues
            if removed:
                deltas.append(f"removed {', '.join(removed)}")
            if deltas:
                result[k] = "; ".join(deltas)
        elif left != right:
            result[k] = f"{shorten_text(str(left))} != {shorten_text(str(right))}"

    return result


def count_values(obj: dict[str, Any]) -> int:
    total = 0
    for value in obj.values():
        if isinstance(value, (str, int, bool, float)):
            total += 1
        elif isinstance(value, dict):
            total += count_values(value)
        elif isinstance(value, (list, set)):
            total += len(value)
        else:
            raise ValueError(f"Unhandled type {type(value).__name__}")

    return total


def find_references(obj: dict[str, Any]) -> set[str]:
    refs = find_dict_prop(obj, REFS)
    return set([_.split("/")[-1] for _ in refs])


def map_operations(paths: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for path, path_data in paths.items():
        path_params = path_data.get(PARAMS)
        for method, op_data in path_data.items():
            op_id = op_data.get(OP_ID)
            if not op_id:
                continue

            op_data[X_PATH] = path
            op_data[X_PATH_PARAMS] = path_params
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


def remove_schema_tags(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)  # copy to make non-destructive

    # "tags" are in the operation data -- using a blind dict could cause properties named "tags" to get removed
    paths = result.get(PATHS, {})
    for path_data in paths.values():
        for op_data in path_data.values():
            op_data.pop(TAGS, None)

    # plus, there may be top-level tags with a description
    result.pop(TAGS, None)

    return result


def set_nullable_not_required(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)

    schemas = result.get(COMPONENTS, {}).get(SCHEMAS, {})
    for schema_value in schemas.values():
        required = schema_value.pop(REQUIRED, None)
        if not required:
            continue
        required = set(required)
        for prop_name, prop_data in schema_value.get(PROPS, {}).items():
            if prop_data.get(NULLABLE, False) and prop_name in required:
                required.remove(prop_name)
        if required:
            schema_value[REQUIRED] = list(required)

    return result


def schema_operations(
    schema: dict[str, Any],
    remove_ops: Optional[set[str]] = None,
    allow_ops: Optional[set[str]] = None,
) -> dict[str, Any]:
    result = deepcopy(schema)

    op_map = map_operations(result.pop(PATHS, {}))

    # make sure all operation_names are in the OAS
    if remove_ops:
        missing_ops = remove_ops - op_map.keys()
        if missing_ops:
            raise ValueError(f"schema is missing: {', '.join(missing_ops)}")
    else:
        missing_ops = allow_ops - op_map.keys()
        if missing_ops:
            raise ValueError(f"schema is missing: {', '.join(missing_ops)}")

        # create the list of operations to remove
        remove_ops = op_map.keys() - allow_ops

    # remove the specified operations from the operations map
    for op_name in remove_ops:
        op_map.pop(op_name)

    # reconstruct the paths
    paths = {}
    for op_name, op_data in op_map.items():
        path = op_data.pop(X_PATH)
        params = op_data.pop(X_PATH_PARAMS, None)
        method = op_data.pop(X_METHOD)
        orig = paths.get(path, {})
        if params and PARAMS not in orig:
            orig[PARAMS] = params
        orig[method] = op_data
        paths[path] = orig
    result[PATHS] = paths

    # figure out all the models that are referenced from the remaining operations
    op_refs = find_references(op_map)
    models = result.get(COMPONENTS, {}).get(SCHEMAS, {})
    model_refs = {
        name: find_references(model)
        for name, model in models.items()
    }
    used_models = unroll(model_refs, op_refs)
    unused_models = models.keys() - used_models

    # remove the unused models
    for name in unused_models:
        models.pop(name)

    # compile a list of tags that are used
    used_tags = set()
    for op_data in op_map.values():
        used_tags.update(set(op_data.get(TAGS, [])))

    # remove unused tags from top-level schema
    tag_defs = result.pop(TAGS, None)
    if tag_defs:
        updated_tags = [t for t in tag_defs if t.get(NAME) in used_tags]
        if updated_tags:
            result[TAGS] = updated_tags

    return result
