#!/usr/bin/env python3
"""Implement the 'oas analyze properties' CLI commands."""
from copy import deepcopy
from enum import Enum
from typing import Annotated
from typing import Any
from typing import Callable

import typer
from rich_objects import console_factory

from openapi_spec_tools.cli.arguments import ExpansionOption
from openapi_spec_tools.cli.arguments import ExpansionType
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import perform_expansion
from openapi_spec_tools.properties import map_model_properties
from openapi_spec_tools.properties import map_parameter_properties
from openapi_spec_tools.properties import map_request_properties
from openapi_spec_tools.properties import map_response_properties
from openapi_spec_tools.types import OasField

app = typer.Typer(no_args_is_help=True, short_help="Inspect things related to properties")

PropertyMap = Callable[[dict[str, Any]], dict[str, set[str]]]


class PropertySource(str, Enum):
    """Kind of property to list."""

    ALL = "all"
    COMPONENTS = "components"
    REQUESTS = "requests"
    RESPONSES = "responses"
    PARAMETERS = "parameters"


_PROPERTY_MAPS: dict[PropertySource, PropertyMap] = {
    PropertySource.COMPONENTS: map_model_properties,
    PropertySource.REQUESTS: map_request_properties,
    PropertySource.RESPONSES: map_response_properties,
    PropertySource.PARAMETERS: map_parameter_properties,
}


def _expand_schema(schema: Any, expansion: ExpansionType, components: dict[str, Any], reference: str | None) -> Any:
    """Expand or flatten one schema object."""
    if not isinstance(schema, dict):
        return schema
    return perform_expansion(expansion, schema, components, reference)


def _expand_parameters(container: dict[str, Any], expansion: ExpansionType, components: dict[str, Any]) -> None:
    """Expand parameter schemas stored on a path item or operation."""
    params = container.get(OasField.PARAMS)
    if not isinstance(params, list):
        return

    expanded = []
    for param in params:
        expanded.append(_expand_schema(param, expansion, components, None))
    container[OasField.PARAMS.value] = expanded


def _expand_spec(spec: dict[str, Any], expansion: ExpansionType) -> dict[str, Any]:
    """Return ``spec`` with component and operation schemas expanded or flattened.

    References are resolved against the original components. ``none`` returns ``spec`` unchanged.
    """
    if expansion == ExpansionType.NONE:
        return spec

    components = spec.get(OasField.COMPONENTS, {})
    if not isinstance(components, dict):
        components = {}

    prepared = deepcopy(spec)
    prepared_components = prepared.get(OasField.COMPONENTS)
    if isinstance(prepared_components, dict):
        for section, models in prepared_components.items():
            if not isinstance(models, dict):
                continue
            for name, model in list(models.items()):
                models[name] = _expand_schema(model, expansion, components, f"{section}/{name}")

    paths = prepared.get(OasField.PATHS)
    if isinstance(paths, dict):
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            _expand_parameters(path_item, expansion, components)
            for method, operation in list(path_item.items()):
                if method == OasField.PARAMS or not isinstance(operation, dict):
                    continue
                _expand_parameters(operation, expansion, components)
                body = operation.get(OasField.REQ_BODY)
                if isinstance(body, dict):
                    operation[OasField.REQ_BODY.value] = _expand_schema(body, expansion, components, None)
                responses = operation.get(OasField.RESPONSES)
                if not isinstance(responses, dict):
                    continue
                for code, response in list(responses.items()):
                    responses[code] = _expand_schema(response, expansion, components, None)
    return prepared


def _merge_property_maps(*prop_maps: dict[str, set[str]]) -> dict[str, set[str]]:
    """Combine property maps, keeping every owner for a shared property name."""
    found: dict[str, set[str]] = {}
    for prop_map in prop_maps:
        for name, owners in prop_map.items():
            found.setdefault(name, set()).update(owners)
    return found


@app.command(name="list", short_help="List properties in OpenAPI spec")
def properties_list(
    filename: OpenApiFilenameArgument,
    search: Annotated[
        str | None,
        typer.Option("--contains", help="Search for this value in the property names"),
    ] = None,
    source: Annotated[
        PropertySource,
        typer.Option(
            "--source",
            case_sensitive=False,
            help="Property sources to list. Models come from components, and others come from operations.",
        ),
    ] = PropertySource.ALL,
    expansion: ExpansionOption = "none",
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level)
    spec = _expand_spec(open_oas_with_error_handling(filename), expansion)

    collectors = _PROPERTY_MAPS.values() if source == PropertySource.ALL else (_PROPERTY_MAPS[source],)
    properties = _merge_property_maps(*(collector(spec) for collector in collectors))
    names = sorted(properties)
    if search:
        needle = search.lower()
        names = [_ for _ in names if needle in _.lower()]

    console = console_factory()
    match_info = f" matching '{search}'" if search else ""
    if not names:
        console.print(f"No properties found{match_info}")
        return

    console.print(f"Found {len(names)} properties{match_info}:")
    for name in names:
        console.print(f"{INDENT}{name}:")
        for parent in sorted(properties[name]):
            console.print(f"{INDENT}{INDENT}{parent}")

    return
