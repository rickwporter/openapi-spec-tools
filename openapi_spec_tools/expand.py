"""Collection of utilities used for expanding the OpenAPI spec models."""
from copy import deepcopy
from typing import Any

from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import reference_classname
from openapi_spec_tools.utils import short_ref


def merge_schema(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge ``overlay`` onto ``base``, combining properties and required lists.

    A property in ``overlay`` replaces a property of the same name in ``base``.
    """
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key == OasField.PROPS and isinstance(value, dict):
            properties = dict(merged.get(key, {}))
            properties.update(deepcopy(value))
            merged[key] = properties
        elif key == OasField.REQUIRED and isinstance(value, list):
            merged[key] = list(dict.fromkeys([*merged.get(key, []), *value]))
        else:
            merged[key] = deepcopy(value)
    return merged


def expand_schema(
    schema: dict[str, Any] | None,
    components: dict[str, Any],
    reference: str | None = None,
) -> dict[str, Any]:
    """Resolve ``$ref`` values and merge ``allOf`` items into one schema.

    Expansion walks the schema, including nested property schemas. Later ``allOf`` items
    replace properties that share a name. A reference already being expanded is skipped.
    A resolved reference records its short name in ``x-reference``. Properties brought in
    by that reference record the same name, unless they already have an ``x-reference``.
    ``components`` is the OpenAPI components object used to resolve references.
    """

    def _model(reference: str) -> dict[str, Any] | None:
        """Return the component schema named by ``reference``."""
        value: Any = components
        for key in short_ref(reference).split('/'):
            if not key or not isinstance(value, dict):
                return None
            value = value.get(key)
            if not value:
                return None
        return value

    def _mark_reference_properties(schema: dict[str, Any], class_name: str) -> None:
        """Record ``class_name`` on properties brought in by a resolved reference."""
        properties = schema.get(OasField.PROPS)
        if not isinstance(properties, dict):
            return
        for prop in properties.values():
            if isinstance(prop, dict):
                prop.setdefault(OasField.X_REF.value, class_name)

    def _expand_value(value: Any, seen: set[str]) -> Any:
        """Expand schemas contained in a dict or list."""
        if isinstance(value, dict):
            return _expand(value, seen)
        if isinstance(value, list):
            return [_expand_value(item, seen) for item in value]
        return value

    def _expand(model: dict[str, Any] | None, seen: set[str]) -> dict[str, Any]:
        """Expand one schema, skipping references already on the stack."""
        if not model:
            return {}

        pending = deepcopy(model)
        resolved: dict[str, Any] = {}

        reference = pending.pop(OasField.REFS, None)
        if reference and reference not in seen:
            seen.add(reference)
            target = _model(reference)
            resolved = _expand(target, seen)
            seen.remove(reference)
            if target:
                class_name = reference_classname(reference)
                resolved[OasField.X_REF.value] = class_name
                _mark_reference_properties(resolved, class_name)

        for item in pending.pop(OasField.ALL_OF, None) or []:
            resolved = merge_schema(resolved, _expand(item, seen))

        if pending:
            resolved = merge_schema(resolved, pending)

        return {key: _expand_value(value, seen) for key, value in resolved.items()}

    result = _expand(schema, set())
    if reference:
        _mark_reference_properties(result, reference_classname(reference))

    return result
