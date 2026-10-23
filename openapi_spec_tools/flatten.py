"""Collection of utilities for flattening the OAS models."""

from copy import deepcopy
from typing import Any

from openapi_spec_tools.constants import NULL_TYPES
from openapi_spec_tools.constants import SIMPLE_TYPES
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import reference_classname


def _reference_name(model: dict[str, Any]) -> str | None:
    """Return the short class name for a schema's ``$ref`` or ``x-reference``."""
    reference = model.get(OasField.REFS)
    if not isinstance(reference, str) or not reference:
        reference = model.get(OasField.X_REF)
    if isinstance(reference, str) and reference:
        return reference_classname(reference)
    return None


def _apply_reference(prop: Any, inherited: str | None) -> Any:
    """Record the lowest-level reference class on ``prop``."""
    if not isinstance(prop, dict):
        return prop

    own = prop.get(OasField.REFS)
    if isinstance(own, str) and own:
        prop[OasField.X_REF.value] = reference_classname(own)
        return prop
    if not prop.get(OasField.X_REF) and inherited:
        prop[OasField.X_REF.value] = inherited
    return prop


def _add_x_field(prop: Any, name: str) -> Any:
    """Record the lowest-level property name in ``x-field``."""
    if isinstance(prop, dict):
        prop[OasField.X_FIELD.value] = name.rsplit(".", maxsplit=1)[-1]
    return prop


def _add_parent(prop: Any, parent: str) -> Any:
    """Prepend ``parent`` to the property's ``x-parents`` chain."""
    if not isinstance(prop, dict):
        return prop

    existing = prop.get(OasField.X_PARENTS)
    if isinstance(existing, list):
        chain = existing
    elif existing is None:
        chain = []
    else:
        chain = [existing]
    prop[OasField.X_PARENTS.value] = [parent, *chain]
    return prop


def _prefixed_required(name: str, prop: dict[str, Any]) -> list[str]:
    """Prefix a cascaded property's required names with ``name``."""
    required = prop.get(OasField.REQUIRED)
    if not isinstance(required, list):
        return []
    return [f"{name}.{item}" for item in required]


def _mark_required(prop: Any, required: bool) -> Any:
    """Set ``required`` when this value is a property schema."""
    if not isinstance(prop, dict) or isinstance(prop.get(OasField.REQUIRED), list):
        return prop

    own = prop.get(OasField.REQUIRED)
    prop[OasField.REQUIRED.value] = required and own if isinstance(own, bool) else required
    return prop


# Nested schemas that represent child properties, and so inherit ``readOnly``.
_READ_ONLY_SCHEMA_FIELDS = frozenset(
    {
        OasField.ADDITIONAL_PROPS,
        OasField.ALL_OF,
        OasField.ANY_OF,
        OasField.ITEMS,
        OasField.ONE_OF,
    }
)


def _is_read_only(model: Any) -> bool:
    """Return whether ``model`` sets ``readOnly`` to true."""
    return isinstance(model, dict) and model.get(OasField.READ_ONLY) is True


def _merge_read_only(model: dict[str, Any], parent_read_only: bool, child: Any) -> None:
    """Keep ``readOnly`` true when either merged schema is read-only."""
    if parent_read_only or _is_read_only(child):
        model[OasField.READ_ONLY.value] = True


def _collection_type(model: dict[str, Any]) -> str | None:
    """Return ``array`` when the schema is an array, including a nullable array."""
    schema_type = model.get(OasField.TYPE)
    if schema_type == "array":
        return schema_type
    if not isinstance(schema_type, list):
        return None
    kinds = [item for item in schema_type if item not in NULL_TYPES]
    if kinds == ["array"]:
        return "array"
    return None


def _is_complex(schema: dict[str, Any]) -> bool:
    """Return whether ``schema`` has nested properties.

    A schema is complex when it has properties, or when an array ``items`` schema or the first
    ``allOf``, ``anyOf``, or ``oneOf`` entry is complex. Scalar types are not complex.
    """
    properties = schema.get(OasField.PROPS)
    if isinstance(properties, dict) and properties:
        return True

    items = schema.get(OasField.ITEMS)
    if isinstance(items, dict) and _is_complex(items):
        return True

    types = schema.get(OasField.TYPE)
    if types and isinstance(types, (list, str)):
        types = set(types if isinstance(types, list) else [types])
        return not types.issubset(SIMPLE_TYPES)

    for field in (OasField.ALL_OF, OasField.ANY_OF, OasField.ONE_OF):
        nested = schema.get(field)
        if isinstance(nested, list) and nested and isinstance(nested[0], dict) and _is_complex(nested[0]):
            return True
    return False


def _collection_requires_items(model: dict[str, Any], ancestor_required: bool) -> bool:
    """Return whether fields taken from a collection item stay required.

    Item fields are required only when the collection itself is required and ``minItems`` is greater
    than zero. A missing ``minItems`` means the collection may be empty, so its fields are optional.
    """
    if not ancestor_required:
        return False
    min_items = model.get(OasField.MIN_ITEMS, 0)
    return isinstance(min_items, int) and min_items > 0


def _flatten_collection(model: dict[str, Any], ancestor_required: bool = True) -> bool:
    """Treat an array of complex items as one item.

    The item schema replaces the array. ``x-forced-single`` is set and ``x-collection`` is omitted.
    ``readOnly`` true on the array or the items schema is kept. Required fields on the item stay
    required only when the collection is required and ``minItems`` is greater than zero.
    """
    collection_type = _collection_type(model)
    if collection_type is None:
        return False
    items = model.get(OasField.ITEMS)
    if not isinstance(items, dict) or items is model:
        return False
    while _apply_any_of(items) or _apply_one_of(items):
        pass
    complex = _is_complex(items)

    if not _collection_requires_items(model, ancestor_required) and OasField.REQUIRED.value in items:
        items[OasField.REQUIRED.value] = False

    parent_read_only = _is_read_only(model)
    model.pop(OasField.ITEMS.value, None)
    model.pop(OasField.TYPE.value, None)
    model.update(items)
    _merge_read_only(model, parent_read_only, items)
    if complex:
        model[OasField.X_SINGLE.value] = True
        model.pop(OasField.X_COLLECT.value, None)
    else:
        model.pop(OasField.X_SINGLE.value, None)
        model[OasField.X_COLLECT.value] = collection_type

    return True


def _mark_single(prop: Any, forced_single: bool) -> Any:
    """Mark a property that came from a multi-property collection."""
    if forced_single and isinstance(prop, dict):
        prop[OasField.X_SINGLE.value] = True
    return prop


def _flatten_value(value: Any, ancestor_read_only: bool = False) -> Any:
    """Flatten schemas contained in a dict or list."""
    if isinstance(value, dict):
        return _flatten_model(value, ancestor_read_only=ancestor_read_only)
    if isinstance(value, list):
        return [_flatten_value(item, ancestor_read_only) for item in value]
    return value


def _flatten_properties(
    properties: dict[str, Any],
    reference: str | None,
    required_names: set[str],
    ancestor_required: bool,
    forced_single: bool,
    ancestor_read_only: bool,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Return flattened properties and the required-name replacements.

    ``ancestor_read_only`` true is copied onto every property.
    """
    flat: dict[str, Any] = {}
    replacements: dict[str, list[str]] = {}
    for name, raw_prop in properties.items():
        level_required = ancestor_required and name in required_names
        prop = (
            _flatten_model(raw_prop, level_required, ancestor_read_only)
            if isinstance(raw_prop, dict)
            else raw_prop
        )
        nested = prop.get(OasField.PROPS) if isinstance(prop, dict) else None
        if isinstance(nested, dict) and nested:
            replacements[name] = _prefixed_required(name, prop)
            for sub_name, sub_prop in nested.items():
                full_name = f"{name}.{sub_name}"
                updated = _apply_reference(_add_parent(sub_prop, name), reference)
                flat[full_name] = _add_x_field(_mark_single(updated, forced_single), full_name)
        else:
            marked = _mark_single(_mark_required(prop, level_required), forced_single)
            flat[name] = _add_x_field(_apply_reference(marked, reference), name)
            replacements[name] = [name]
    return flat, replacements


def _apply_any_of(model: dict[str, Any]) -> bool:
    """Merge the first ``anyOf`` schema onto ``model`` when that item is complex.

    Simple scalar alternatives stay as ``anyOf``. Keys already on ``model`` stay when the chosen
    item does not set them. ``readOnly`` true on either schema is kept.
    """
    any_of = model.get(OasField.ANY_OF)
    if not isinstance(any_of, list) or not any_of or not isinstance(any_of[0], dict):
        return False
    chosen = any_of[0]
    if not _is_complex(chosen):
        return False

    parent_read_only = _is_read_only(model)
    model.pop(OasField.ANY_OF.value, None)
    model.update(chosen)
    _merge_read_only(model, parent_read_only, chosen)
    return True


def _apply_one_of(model: dict[str, Any]) -> bool:
    """Merge the first ``oneOf`` schema onto ``model``.

    Keys already on ``model`` stay when the chosen item does not set them.
    ``readOnly`` true on either schema is kept.
    """
    one_of = model.get(OasField.ONE_OF)
    if not isinstance(one_of, list) or not one_of or not isinstance(one_of[0], dict):
        return False

    chosen = one_of[0]
    parent_read_only = _is_read_only(model)
    model.pop(OasField.ONE_OF.value, None)
    model.update(chosen)
    _merge_read_only(model, parent_read_only, chosen)
    return True


def _flatten_model(
    model: dict[str, Any],
    ancestor_required: bool = True,
    ancestor_read_only: bool = False,
) -> dict[str, Any]:
    """Flatten one schema, hoisting cascaded properties into the parent map."""
    if ancestor_read_only:
        model[OasField.READ_ONLY.value] = True

    if _apply_one_of(model):
        return _flatten_model(model, ancestor_required, ancestor_read_only)

    if _apply_any_of(model):
        return _flatten_model(model, ancestor_required, ancestor_read_only)

    if _flatten_collection(model, ancestor_required):
        return _flatten_model(model, ancestor_required, ancestor_read_only)

    read_only = _is_read_only(model)
    for key, value in list(model.items()):
        if key == OasField.PROPS:
            continue
        model[key] = _flatten_value(value, read_only and key in _READ_ONLY_SCHEMA_FIELDS)

    properties = model.get(OasField.PROPS)
    required = model.get(OasField.REQUIRED)
    if isinstance(properties, dict):
        required_names = set(required) if isinstance(required, list) else set()
        flat, replacements = _flatten_properties(
            properties,
            _reference_name(model),
            required_names,
            ancestor_required,
            bool(model.get(OasField.X_SINGLE)),
            read_only,
        )
        model[OasField.PROPS.value] = flat
        if isinstance(required, list):
            model[OasField.REQUIRED.value] = [
                renamed
                for name in required
                for renamed in replacements.get(name, [name])
            ]
    return model


def flatten_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Consolidate nested, fully expanded objects into dotted dictionary of property names.

    A property that has its own properties is replaced by those properties. Each consolidated
    name is ``<parent_name>.<property_name>``. ``x-parents`` concatenates the parent names in
    the chain, from the outermost parent to the immediate parent. ``x-field`` is the lowest-level
    property name, so ``home.address.zip_code`` records ``zip_code``. ``x-reference`` is the
    ``reference_classname()`` name of the lowest-level ``$ref`` class that contains the property.
    A property's ``required`` value is true only when that property and every ancestor are required.
    Fields taken from an array item are required only when that array is required and ``minItems`` is
    greater than zero.
    ``readOnly`` true on a schema or property is copied onto every nested property. ``readOnly`` false
    is not copied downward. A property that sets ``readOnly`` true stays read-only when its parent is
    false or omits ``readOnly``. A schema with ``anyOf`` uses the first item when that item is complex.
    An item is complex when it has properties, or when a nested array, ``allOf``, ``anyOf``, or ``oneOf``
    leads to properties. Simple scalar alternatives stay in ``anyOf``. Keys already on the schema remain
    when that item does not set them. A schema with ``oneOf`` uses the first item in that list. Keys already
    on the schema remain when that item does not set them, so a description carries through. An array
    of complex items
    is replaced by one item schema, marked ``x-forced-single``, and does not record ``x-collection``.
    An array of a simple type, such as string, boolean, number, or integer, takes that items type,
    drops ``items``, and records ``x-collection`` as ``array``. Schemas nested in other fields are
    flattened the same way. The input schema is not modified.
    """
    if not schema:
        return {}
    return _flatten_model(deepcopy(schema))

