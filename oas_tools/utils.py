from copy import deepcopy
from itertools import zip_longest
from typing import Any
from typing import Optional

import yaml

from oas_tools.constants import Fields


def open_oas(filename: str) -> Any:
    """
    Open the specified filename, and return the dictionary.
    """
    with open(filename, "r") as fp:
        return yaml.safe_load(fp)


def unroll(full_set: dict[str, set[str]], items: set[str]) -> set[str]:
    """
    Utility to unroll all the references from items.

    The 'full_set' is a mapping of names to references, and the 'items' is
    the initial set of names to look for.

    The return is the set of all items of the referenced from the inputs.

    Example
    =======
       full_set = {
                    a: {b},
                    b: {c, d},
                    c: {},
                    d: {e},
                    e: {},
                }
        items = {b, c}

       result = {b, c, d, e}
    """
    result = deepcopy(items)

    for i in items:
        sub = full_set.get(i)
        if sub:
            result.update(unroll(full_set, sub))

    return result


def find_dict_prop(obj: dict[str, Any], prop_name: str) -> set[str]:
    """
    Used to get the string values of all the 'prop_name' properties in the 'obj'. This
    works recursively, so it can be used to walk everything in 'obj' (and not just the
    top level).
    """
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
    """
    Used to get the string values of all the 'prop_name' properties in the list of dictionaries 'items'.
    """
    result = set()
    for item in items:
        if isinstance(item, dict):
            result.update(find_dict_prop(item, prop_name))

    return result


def shorten_text(text: str, max_len: int = 16) -> str:
    """
    Shortens 'text' to a maximum length of 'max_len' (including the elipsis)
    """
    if len(text) >= max_len:
        text = text[:max_len - 3] + "..."
    return text


def find_diffs(lhs: dict[str, Any], rhs: dict[str, Any]) -> dict[str, Any]:
    """
    Provides a summary of the differences between the left and right hand-side dictionaries.

    Generally, the lefthand side ('lhs') is the original, and the righthand side ('rhs') is
    the updated dictionary. Generally, this tells you which items have been added or removed
    without providing all the details. It recursively walks the pair of dictionaries to provide
    the differences.
    """
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
            else:
                for index, (lvalue, rvalue) in enumerate(zip_longest(left, right)):
                    # recursive call to find sub-object deltas
                    vdiff = find_diffs(lvalue, rvalue)
                    if vdiff:
                        item_key = f"{k}[{index}]"
                        result[item_key] = vdiff
        elif isinstance(left, list) and left:
            # simple list items here
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
    """
    Recursively walks the 'obj' dictionary to count the simple values (e.g. int, float, bool).

    This is useful for counting the number of differences as determined by 'find_diffs()'.
    """
    total = 0
    for key, value in obj.items():
        if isinstance(value, (str, int, bool, float)):
            total += 1
        elif isinstance(value, dict):
            total += count_values(value)
        elif isinstance(value, (list, set)):
            for item in value:
                if isinstance(item, dict):
                    total += count_values(item)
                else:
                    total += 1
        else:
            raise ValueError(f"Unhandled type {type(value).__name__} for '{key}'")

    return total


def find_references(obj: dict[str, Any]) -> set[str]:
    """
    Walks the 'obj' dictionary to find all the reference values (e.g. "$ref").
    """
    refs = find_dict_prop(obj, Fields.REFS)
    return set([_.split("/")[-1] for _ in refs])


def map_operations(paths: dict[str, Any]) -> dict[str, Any]:
    """
    Takes the 'paths' dictionary and transforms into an dictionary with the 'operationId'
    as the key. It puts the path, path paramters, and method into the individual items
    of the new dictionary.

    The resulting map is useful for dealing with operations (e.g. filtering).

    Example
    =======

    Input:
    ------
      /v1/pets/{petId}:
        parameters:
        - name: petId
          in: path
          type: string
        get:
          operationId: getPet
          responses:
            '200':
              description: Pet object
              # content omitted for example
        delete:
          operationId: deletePet
          responses:
             '204':
               description: Nothing returned on successful delete

    Output:
    -------
    {
      getPet: {
        operationId: getPet,
        responses: {'200': {description: Pet object}},
        x-method: get,
        x-path: /v1/pets/{petId},
        x-path-params: [{name: petId, in: path, type: string}],
      },
      deletePet: {
        operationId: deletePet,
        responses: {'204': {description: Nothing returned on successful delete}}
        x-method: delete,
        x-path: /v1/pets/{petId},
        x-path-params: [{name: petId, in: path, type: string}],
      },
    }
    """
    result = {}
    for path, path_data in paths.items():
        path_params = path_data.pop(Fields.PARAMS, None)
        for method, op_data in path_data.items():
            op_id = op_data.get(Fields.OP_ID)
            op_data[Fields.X_PATH] = path
            op_data[Fields.X_PATH_PARAMS] = path_params
            op_data[Fields.X_METHOD] = method
            result[op_id] = op_data

    return result


def find_paths(paths: dict[str, Any], search: Optional[str] = None, sub_paths: bool = False) -> dict[str, Any]:
    """
    Searches the 'paths' dictionary for path names including the 'search' string (if provided).
    """
    def anon(s: str) -> str:
        return s.lower().rstrip("/")

    result = {}
    needle = None if search is None else anon(search)
    for path, path_data in paths.items():
        if needle:
            name = anon(path)
            if not sub_paths and name != needle:
                continue
            if sub_paths and not name.startswith(needle):
                continue
        result[path] = path_data

    return result


def remove_schema_tags(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Removes all 'tags' from the output schema.

    Using code generation, the 'tags' values often group operations into different. This will cause
    extra classes to be required for only a handful of operations. For this reason, it can be
    useful to remove the tags to reduce the number of client classes.
    """
    result = deepcopy(schema)  # copy to make non-destructive

    # "tags" are in the operation data -- using a blind dict could cause properties named "tags" to get removed
    paths = result.get(Fields.PATHS, {})
    for path_data in paths.values():
        for op_data in path_data.values():
            op_data.pop(Fields.TAGS, None)

    # plus, there may be top-level tags with a description
    result.pop(Fields.TAGS, None)

    return result


def set_nullable_not_required(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Removes any 'nullable: true' property from the 'required' list.

    Some generated clients have a difficult time distinguishing between a property
    that is 'null', and one that is not present. By removing the property from
    the required list, you can avoid some of these issues.

    Example
    =======

    Input:
    ------
    Pet:
      type: object
      properties:
        id:
          type: integer
          format: int64
        name:
          type: string
        owner:
          type: string
          nullable: true
      required:
        - id
        - name
        - owner

    Output:
    -------
    Pet:
      type: object
      properties:
        id:
          type: integer
          format: int64
        name:
          type: string
        owner:
          type: string
          nullable: true
      required:
        - id
        - name
    """
    result = deepcopy(schema)

    schemas = result.get(Fields.COMPONENTS, {}).get(Fields.SCHEMAS, {})
    for schema_value in schemas.values():
        required = schema_value.pop(Fields.REQUIRED, None)
        if not required:
            continue
        required = set(required)
        for prop_name, prop_data in schema_value.get(Fields.PROPS, {}).items():
            if prop_data.get(Fields.NULLABLE, False) and prop_name in required:
                required.remove(prop_name)
        if required:
            schema_value[Fields.REQUIRED] = list(required)

    return result


def schema_operations_filter(
    schema: dict[str, Any],
    remove_ops: Optional[set[str]] = None,
    allow_ops: Optional[set[str]] = None,
) -> dict[str, Any]:
    """
    Filters the schema operations to either the 'allow_ops' or those not in the 'remove_ops'.

    This operation also removes unreferenced components and tags. For example, removing a
    'listPets' operation would remove the '#/components/schemas/Pets' object that was only
    used by that operation.
    """
    result = deepcopy(schema)

    op_map = map_operations(result.pop(Fields.PATHS, {}))

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
        path = op_data.pop(Fields.X_PATH)
        params = op_data.pop(Fields.X_PATH_PARAMS, None)
        method = op_data.pop(Fields.X_METHOD)
        orig = paths.get(path, {})
        if params and Fields.PARAMS not in orig:
            orig[Fields.PARAMS] = params
        orig[method] = op_data
        paths[path] = orig
    result[Fields.PATHS] = paths

    # figure out all the models that are referenced from the remaining operations
    op_refs = find_references(op_map)
    models = result.get(Fields.COMPONENTS, {}).get(Fields.SCHEMAS, {})
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
        used_tags.update(set(op_data.get(Fields.TAGS, [])))

    # remove unused tags from top-level schema
    tag_defs = result.pop(Fields.TAGS, None)
    if tag_defs:
        updated_tags = [t for t in tag_defs if t.get(Fields.NAME) in used_tags]
        if updated_tags:
            result[Fields.TAGS] = updated_tags

    return result
