"""Utilties for analyzing and manipulating OpenAPI specifications."""
import json
from copy import deepcopy
from itertools import zip_longest
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

import yaml

from openapi_spec_tools.types import OasField

NULL_TYPES = {'null', '"null"', "'null'"}


def open_oas(filename: str) -> Any:
    """Open the specified filename, and return the dictionary."""
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(filename)

    with open(filename, "r", encoding="utf-8", newline="\n") as fp:
        if filename.endswith('json'):
            return json.load(fp)
        return yaml.safe_load(fp)


def unroll(full_set: dict[str, set[str]], items: set[str]) -> set[str]:
    """Unroll all the references from items.

    The 'full_set' is a mapping of names to references, and the 'items' is
    the initial set of names to look for.

    The return is the set of all items of the referenced from the inputs.

    Example:
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
    """Get the string values of all the 'prop_name' properties in the 'obj'.

    This works recursively, so it can be used to walk everything in 'obj' (and not just the top level).
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
    """Get the string values of all the 'prop_name' properties in the list of dictionaries 'items'."""
    result = set()
    for item in items:
        if isinstance(item, dict):
            result.update(find_dict_prop(item, prop_name))

    return result


def shorten_text(text: str, max_len: int = 16) -> str:
    """Shorten 'text' to a maximum length of 'max_len' (including the elipsis)."""
    if len(text) >= max_len:
        text = text[:max_len - 3] + "..."
    return text


def _result_add_message(result: dict[str, Any], keys: set[str], msg: str) -> None:
    """Add the provided message to the result for the provided keys."""
    for k in keys:
        result[k] = msg

    return


def _result_is_none(result: dict[str, Any], key: str, left: Any, right: Any) -> None:
    """Update result with a message if one of the two values is None."""
    if left == right:
        return
    if left is None:
        result[key] = "original is None"
    if right is None:
        result[key] = "updated is None"

    return


def _result_complex_list_diff(result: dict[str, Any], key: str, left: list[Any], right: list[Any]) -> None:
    """Update result with message about differences between lists of complex items."""
    for index, (lvalue, rvalue) in enumerate(zip_longest(left, right)):
        # call into find_diffs to obtain list item object deltas
        vdiff = find_diffs(lvalue, rvalue)
        if vdiff:
            item_key = f"{key}[{index}]"
            result[item_key] = vdiff

    return


def _result_simple_list_diff(result: dict[str, Any], key: str, left: list[Any], right: list[Any]) -> None:
    """Update result with message about differences between lists of simple items."""
    lvalues = set(left)
    rvalues = set(right)
    deltas = []
    added = rvalues - lvalues
    if added:
        deltas.append(f"added {', '.join(sorted(added))}")
    removed = lvalues - rvalues
    if removed:
        deltas.append(f"removed {', '.join(sorted(removed))}")
    if deltas:
        result[key] = "; ".join(deltas)

    return


def find_diffs(lhs: dict[str, Any], rhs: dict[str, Any]) -> dict[str, Any]:
    """Provide a summary of the differences between the left and right hand-side dictionaries.

    Generally, the lefthand side ('lhs') is the original, and the righthand side ('rhs') is
    the updated dictionary. Generally, this tells you which items have been added or removed
    without providing all the details. It recursively walks the pair of dictionaries to provide
    the differences.
    """
    result = {}
    assert isinstance(lhs, dict) and isinstance(rhs, dict)
    lkeys = set(lhs.keys())
    rkeys = set(rhs.keys())

    _result_add_message(result, rkeys - lkeys, "added")
    _result_add_message(result, lkeys - rkeys, "removed")

    common = lkeys & rkeys
    for k in common:
        left = lhs[k]
        right = rhs[k]
        if left is None or right is None:
            # avoids failures due to trying to treat right as dict/list
            _result_is_none(result, k, left, right)
        elif isinstance(left, dict):
            # recursive call to find sub-object deltas
            diffs = find_diffs(left, right)
            if diffs:
                result[k] = diffs
        elif isinstance(left, list) and left and isinstance(left[0], dict):
            if len(left) != len(right):
                result[k] = f"different lengths: {len(left)} != {len(right)}"
            else:
                _result_complex_list_diff(result, k, left, right)
        elif isinstance(left, list) and left:
            _result_simple_list_diff(result, k, left, right)
        elif left != right:
            result[k] = f"{shorten_text(str(left))} != {shorten_text(str(right))}"

    return result


def count_values(obj: dict[str, Any]) -> int:
    """Recursively walk the 'obj' dictionary to count the simple values (e.g. int, float, bool).

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


def short_ref(full_name: str) -> str:
    """Get the shorter reference name (drops the '#/component')."""
    values = [
        part for part in full_name.split('/')
        if part and part not in ('#', OasField.COMPONENTS.value)
    ]
    return '/'.join(values)


def find_references(obj: dict[str, Any]) -> set[str]:
    """Walk the 'obj' dictionary to find all the reference values (e.g. "$ref")."""
    refs = find_dict_prop(obj, OasField.REFS)
    return {short_ref(_) for _ in refs}



def model_references(models: dict[str, Any]) -> set[str]:
    """Create a complete map of model names to their references."""
    return {name: find_references(body) for name, body in models.items()}


def model_filter(models: dict[str, Any], references: set[str]) -> dict[str, Any]:
    """Filter the models to those which are referenced.

    Includes direct and indirect references.
    """
    model_ref_map = model_references(models)
    used_models = unroll(model_ref_map, references)

    return {name: models[name] for name in used_models}


def models_referenced_by(models: dict[str, Any], model_name: str) -> set[str]:
    """Find a list of other models which reference the provided model."""
    referenced_by = {}
    for name, body in models.items():
        refs = find_references(body)
        for r in refs:
            curr = referenced_by.get(r, set())
            curr.add(name)
            referenced_by[r] = curr

    return unroll(referenced_by, referenced_by.get(model_name, set()))


def map_models(comonents: dict[str, Any]) -> dict[str, Any]:
    """Flatten the components into a 1 layer map."""
    models = {}
    for component, values in comonents.items():
        for name, data in values.items():
            models[f"{component}/{name}"] = data

    return models


def unmap_models(models: dict[str, Any]) -> dict[str, Any]:
    """Reconstitutes the components section."""
    # re-organize models into sub-sections
    components = {}
    for full_name, model_def in models.items():
        parts = full_name.split('/')
        comp_name = parts[0]
        model_name = parts[1]
        temp = components.get(comp_name, {})
        temp[model_name] = model_def
        components[comp_name] = temp

    return components


def model_full_name(models: dict[str, Any], name: str) -> Optional[str]:
    """Search for a model matching the specified name. The name may be a partial name."""
    if name in models:
        return name

    matches = [k for k in models.keys() if name == k.split('/')[-1]]
    if len(matches) == 1:
        return matches[0]

    return None


def map_operations(paths: dict[str, Any]) -> dict[str, Any]:
    """Create map of operationId to path data.

    Takes the 'paths' dictionary and transforms into an dictionary with the 'operationId'
    as the key. It puts the path, path paramters, and method into the individual items
    of the new dictionary.

    The resulting map is useful for dealing with operations (e.g. filtering).

    Example:
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
        local_path = deepcopy(path_data)
        path_params = local_path.pop(OasField.PARAMS, None)
        for method, op_data in local_path.items():
            op_id = op_data.get(OasField.OP_ID)
            op_data[OasField.X_PATH.value] = path
            op_data[OasField.X_PATH_PARAMS.value] = path_params
            op_data[OasField.X_METHOD.value] = method
            result[op_id] = op_data

    return result


def find_paths(paths: dict[str, Any], search: Optional[str] = None, sub_paths: bool = False) -> dict[str, Any]:
    """Search the 'paths' dictionary for path names including the 'search' string (if provided)."""
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
    """Remove all 'tags' from the output schema.

    Using code generation, the 'tags' values often group operations into different. This will cause
    extra classes to be required for only a handful of operations. For this reason, it can be
    useful to remove the tags to reduce the number of client classes.
    """
    result = deepcopy(schema)  # copy to make non-destructive

    # "tags" are in the operation data -- using a blind dict could cause properties named "tags" to get removed
    paths = result.get(OasField.PATHS, {})
    for path_data in paths.values():
        for op_data in path_data.values():
            # NOTE: parameters are a list, not a dict
            if not isinstance(op_data, dict):
                continue
            op_data.pop(OasField.TAGS, None)

    # plus, there may be top-level tags with a description
    result.pop(OasField.TAGS, None)

    return result


def _is_nullable(prop_data: dict[str, Any]) -> bool:
    """Determine if a property is nullable."""
    # this handles the OAS 3.0 style where it is denoted by a `nullable: true`
    if prop_data.get(OasField.NULLABLE, False):
        return True

    def _includes_null(types: Union[str, list[str]]) -> bool:
        if isinstance(types, str) and types in NULL_TYPES:
            return True
        return any(x in types for x in NULL_TYPES)

    # this handles the OAS 3.1 style where the `type` field has a `null` value
    if _includes_null(prop_data.get(OasField.TYPE, [])):
        return True

    # iterate through all the options in anyOf/oneOf
    for tag in [OasField.ANY_OF, OasField.ONE_OF]:
        for item in prop_data.get(tag, []):
            if _includes_null(item.get(OasField.TYPE, [])):
                return True

    return False


def set_nullable_not_required(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove any 'nullable: true' property from the 'required' list.

    Some generated clients have a difficult time distinguishing between a property
    that is 'null', and one that is not present. By removing the property from
    the required list, you can avoid some of these issues.

    Example:
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

    schemas = result.get(OasField.COMPONENTS, {}).get(OasField.SCHEMAS, {})
    for schema_value in schemas.values():
        required = schema_value.pop(OasField.REQUIRED, None)
        if not required:
            continue
        required = set(required)
        for prop_name, prop_data in schema_value.get(OasField.PROPS, {}).items():
            if _is_nullable(prop_data) and prop_name in required:
                required.remove(prop_name)
        if required:
            schema_value[OasField.REQUIRED.value] = sorted(required)

    return result


def schema_operations_filter(
    schema: dict[str, Any],
    remove: Optional[set[str]] = None,
    allow: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Filter the schema operations to either the 'allow_ops' or those not in the 'remove_ops'.

    This operation also removes unreferenced components and tags. For example, removing a
    'listPets' operation would remove the '#/components/schemas/Pets' object that was only
    used by that operation.
    """
    result = deepcopy(schema)

    op_map = map_operations(result.pop(OasField.PATHS, {}))

    # make sure all operation_names are in the OAS
    if remove:
        missing_ops = remove - op_map.keys()
        if missing_ops:
            raise ValueError(f"schema is missing: {', '.join(missing_ops)}")
    else:
        missing_ops = allow - op_map.keys()
        if missing_ops:
            raise ValueError(f"schema is missing: {', '.join(missing_ops)}")

        # create the list of operations to remove
        remove = op_map.keys() - allow

    # remove the specified operations from the operations map
    for op_name in remove:
        op_map.pop(op_name)

    # reconstruct the paths
    paths = {}
    for op_data in op_map.values():
        path = op_data.pop(OasField.X_PATH)
        params = op_data.pop(OasField.X_PATH_PARAMS, None)
        method = op_data.pop(OasField.X_METHOD)
        orig = paths.get(path, {})
        if params and OasField.PARAMS not in orig:
            orig[OasField.PARAMS.value] = params
        orig[method] = op_data
        paths[path] = orig
    result[OasField.PATHS.value] = paths

    # figure out all the models that are referenced from the remaining operations
    op_refs = find_references(op_map)
    models = map_models(result.pop(OasField.COMPONENTS, {}))
    model_refs = {
        name: find_references(model)
        for name, model in models.items()
    }
    used_models = unroll(model_refs, op_refs)
    models = {
        name: value for name, value in models.items()
        if name in used_models
    }

    result[OasField.COMPONENTS.value] = unmap_models(models)

    # compile a list of tags that are used
    used_tags = set()
    for op_data in op_map.values():
        used_tags.update(set(op_data.get(OasField.TAGS, [])))

    # remove unused tags from top-level schema
    tag_defs = result.pop(OasField.TAGS, None)
    if tag_defs:
        updated_tags = [t for t in tag_defs if t.get(OasField.NAME) in used_tags]
        if updated_tags:
            result[OasField.TAGS.value] = updated_tags

    return result


def map_content_types(schema: dict[str, Any]) -> dict[str, set]:
    """Get map of content-types to operation-id's."""
    content = {}
    for path_data in schema.get(OasField.PATHS, {}).values():
        for method, op_data in path_data.items():
            if method == OasField.PARAMS:
                continue

            op_id = op_data.get(OasField.OP_ID)
            for resp_data in op_data.get(OasField.RESPONSES, {}).values():
                for content_type in resp_data.get(OasField.CONTENT, {}).keys():
                    items = content.get(content_type, set())
                    items.add(op_id)
                    content[content_type] = items

    return content


def remove_property(schema: dict[str, Any], prop_name: str) -> dict[str, Any]:
    """Recursively remove any property matching this name."""
    result = deepcopy(schema)
    if isinstance(result, dict):
        result.pop(prop_name, None)
        dead_keys = set()
        for key, value in result.items():
            if not value:
                continue

            v = remove_property(value, prop_name)
            if not v:
                dead_keys.add(key)
                continue

            result[key] = v

        for key in dead_keys:
            result.pop(key)

    elif isinstance(result, list):
        temp = []
        for item in result:
            if not item:
                temp.append(item)
                continue
            temp.append(remove_property(item, prop_name))
        result = temp

    return result
