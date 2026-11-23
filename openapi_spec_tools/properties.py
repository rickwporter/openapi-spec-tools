"""Utilities for finding property names in an OpenAPI specification.

``$ref`` values are not followed. Nested property names stay on the element that
contains them.
"""
from typing import Any
from typing import Iterator

from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import operation_id

_PARAMETER = "parameter"
_REQUEST = "request"
_RESPONSE = "response"


def _component_source(section: str, name: str) -> str:
    """Return the source id for a component model."""
    return f"component/{section}/{name}"


def _operation_source(op_id: str, kind: str) -> str:
    """Return the source id for an operation parameter, request, or response."""
    return f"{kind}/{op_id}"


def _record_properties(found: dict[str, set[str]], node: Any, owner: str) -> None:
    """Record property names defined under ``node`` for ``owner``."""
    if isinstance(node, list):
        for item in node:
            _record_properties(found, item, owner)
        return
    if not isinstance(node, dict):
        return

    properties = node.get(OasField.PROPS)
    if isinstance(properties, dict):
        for name, prop_schema in properties.items():
            found.setdefault(str(name), set()).add(owner)
            _record_properties(found, prop_schema, owner)

    for keyword in (OasField.ALL_OF, OasField.ANY_OF, OasField.ONE_OF, OasField.ITEMS, OasField.SCHEMA):
        _record_properties(found, node.get(keyword), owner)

    additional = node.get(OasField.ADDITIONAL_PROPS)
    if isinstance(additional, dict):
        _record_properties(found, additional, owner)

    content = node.get(OasField.CONTENT)
    if isinstance(content, dict):
        for media in content.values():
            if isinstance(media, dict):
                _record_properties(found, media.get(OasField.SCHEMA), owner)


def _record_parameter(found: dict[str, set[str]], param: Any, owner: str) -> None:
    """Record a parameter name, and properties defined on its schema, for ``owner``."""
    if isinstance(param, dict):
        name = param.get(OasField.NAME)
        if isinstance(name, str) and name:
            found.setdefault(name, set()).add(owner)

    _record_properties(found, param, owner)


def _record_parameter_list(found: dict[str, set[str]], params: Any, owner: str) -> None:
    """Record each parameter in ``params`` for ``owner``."""
    if not isinstance(params, list):
        return

    for param in params:
        _record_parameter(found, param, owner)


def _iter_operations(paths: Any) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
    """Yield each path item, its operation, and that operation's id."""
    if not isinstance(paths, dict):
        return

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method == OasField.PARAMS or not isinstance(operation, dict):
                continue
            yield path_item, operation, operation_id(operation, str(method), str(path))


def map_model_properties(schema: dict[str, Any]) -> dict[str, set[str]]:
    """Map property names to the component models that define them.

    Every component section is included. Owners use ``component/<section>/<name>``, such as
    ``component/schemas/Pet`` or ``component/parameters/Filter``.
    """
    found: dict[str, set[str]] = {}
    components = schema.get(OasField.COMPONENTS, {})
    if not isinstance(components, dict):
        return found

    for section, models in components.items():
        if not isinstance(models, dict):
            continue
        for name, model in models.items():
            section_name = section.value if isinstance(section, OasField) else section
            _record_properties(found, model, _component_source(section_name, name))
    return found


def map_parameter_properties(schema: dict[str, Any]) -> dict[str, set[str]]:
    """Map operation parameter names, and properties on those schemas, to their operations.

    Path-level parameters are included. Owners use ``parameter/<operationId>``.
    """
    found: dict[str, set[str]] = {}
    for path_item, operation, op_id in _iter_operations(schema.get(OasField.PATHS)):
        owner = _operation_source(op_id, _PARAMETER)
        _record_parameter_list(found, path_item.get(OasField.PARAMS), owner)
        _record_parameter_list(found, operation.get(OasField.PARAMS), owner)
    return found


def map_request_properties(schema: dict[str, Any]) -> dict[str, set[str]]:
    """Map property names defined by operation request bodies.

    Owners use ``request/<operationId>``.
    """
    found: dict[str, set[str]] = {}
    for _path_item, operation, op_id in _iter_operations(schema.get(OasField.PATHS)):
        owner = _operation_source(op_id, _REQUEST)
        _record_properties(found, operation.get(OasField.REQ_BODY), owner)
    return found


def map_response_properties(schema: dict[str, Any]) -> dict[str, set[str]]:
    """Map property names defined by operation responses.

    Owners use ``response/<operationId>``.
    """
    found: dict[str, set[str]] = {}
    for _path_item, operation, op_id in _iter_operations(schema.get(OasField.PATHS)):
        responses = operation.get(OasField.RESPONSES)
        if not isinstance(responses, dict):
            continue
        owner = _operation_source(op_id, _RESPONSE)
        for response in responses.values():
            _record_properties(found, response, owner)
    return found
