"""Collection of utilities used for expanding the OpenAPI spec models."""
import logging
from copy import deepcopy
from typing import Any

from openapi_spec_tools.constants import LOG_CLASS
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import reference_classname
from openapi_spec_tools.utils import schema_summary
from openapi_spec_tools.utils import short_ref

logger = logging.getLogger(f"{LOG_CLASS}.expand")


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
    A reference that cannot be resolved is left in place. A resolved reference records its
    short name in ``x-reference``. Properties brought in by that reference record the same
    name, unless they already have an ``x-reference``. ``components`` is the OpenAPI
    components object used to resolve references.
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

    def _expand_value(value: Any, seen: set[str], name: str | None = None) -> Any:
        """Expand schemas contained in a dict or list."""
        if isinstance(value, dict):
            return _expand(value, seen, name=name)
        if isinstance(value, list):
            base_name = f"{name}." if name else ""
            return [
                _expand_value(item, seen, name=f"{base_name}item[{index}]")
                for index, item in enumerate(value)
            ]
        return value

    def _expand(model: dict[str, Any] | None, seen: set[str], name: str | None = None) -> dict[str, Any]:
        """Expand one schema, skipping references already on the stack."""
        if not model:
            return {}

        pending = deepcopy(model)
        resolved: dict[str, Any] = {}
        base_name = f"{name}." if name else ""

        reference = pending.pop(OasField.REFS, None)
        if reference and reference not in seen:
            seen.add(reference)
            target = _model(reference)
            if target:
                resolved = _expand(target, seen)
                class_name = reference_classname(reference)
                resolved[OasField.X_REF.value] = class_name
                enum = resolved.get(OasField.ENUM)
                if enum and isinstance(enum, list):
                    resolved[OasField.X_ENUM.value] = class_name
                _mark_reference_properties(resolved, class_name)
                logger.debug(f"expanded {name} reference to {class_name}")
            else:
                pending[OasField.REFS.value] = reference
                logger.warning(f"unable to find {reference} model for {name}")
            seen.remove(reference)

        all_of = pending.pop(OasField.ALL_OF, None) or []
        for index, item in enumerate(all_of):
            all_name = f"{base_name}allOf[{index}]"
            expanded = _expand(item, seen, all_name)
            resolved = merge_schema(resolved, expanded)
            logger.debug(f"merged {all_name} of {len(all_of)}: {schema_summary(expanded)}")

        if pending:
            resolved = merge_schema(resolved, pending)

        return {key: _expand_value(value, seen, name=f"{base_name}{key}") for key, value in resolved.items()}

    class_name = reference_classname(reference or "")
    result = _expand(schema, set(), name=class_name)
    if reference:
        _mark_reference_properties(result, reference_classname(reference))

    return result
