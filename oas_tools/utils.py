from copy import deepcopy
from itertools import zip_longest
from typing import Any
from typing import Optional

import yaml

from oas_tools.constants import OP_ID
from oas_tools.constants import PARAMS
from oas_tools.constants import REFS
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
