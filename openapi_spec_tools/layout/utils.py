"""Collection of functions for working the layout files."""
from copy import deepcopy
from pathlib import Path
from typing import Any
from typing import Optional

import yaml

from openapi_spec_tools.layout.types import LayoutField
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationField
from openapi_spec_tools.layout.types import PaginationNames

DEFAULT_START = "main"


def open_layout(filename: str) -> Any:
    """Open the specified filename, and return the dictionary."""
    file = Path(filename)
    if not file.exists():
        raise FileNotFoundError(filename)

    with open(filename, "r", encoding="utf-8", newline="\n") as fp:
        return yaml.safe_load(fp)


def field_to_list(data: dict[str, Any], field: str) -> list[str]:
    """Get the field value and turns CSV text into a list."""
    value = data.get(field)
    if not value:
        return []

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    return [
        i.strip()
        for i in str(value).split(",")
        if i.strip()
    ]


def parse_extras(data: dict[str, Any]) -> dict[str, Any]:
    """Pass through extra user data -- ignore the keys already in the LayoutFields."""
    return {
        k: v
        for k, v in data.items()
        if k not in [v.value for v in LayoutField]
    }


def parse_pagination(data: Optional[dict[str, Any]]) -> Optional[PaginationNames]:
    """Parse the data into pagination parameters."""
    if not data:
        return None

    return PaginationNames(
        page_size=data.get(PaginationField.PAGE_SIZE),
        page_start=data.get(PaginationField.PAGE_START),
        item_start=data.get(PaginationField.ITEM_START),
        items_property=data.get(PaginationField.ITEM_PROP),
        next_header=data.get(PaginationField.NEXT_HEADER),
        next_property=data.get(PaginationField.NEXT_PROP)
    )


def data_to_node(data: dict[str, Any], identifier: str, command: str, item: dict[str, Any]) -> LayoutNode:
    """Recursively convert elements from data to LayoutNodes."""
    description = item.get(LayoutField.DESCRIPTION, "")
    # identifier = item.get(LayoutField.OP_ID) or identifier
    # parse bugs and summary fields into a list
    bugs = field_to_list(item, LayoutField.BUG_IDS)
    summary_fields = field_to_list(item, LayoutField.SUMMARY_FIELDS)
    extra = parse_extras(item)
    pagination = parse_pagination(item.get(LayoutField.PAGINATION))

    children = []
    for op_data in item.get(LayoutField.OPERATIONS, []):
        op_name = op_data.get(LayoutField.NAME)
        sub_id = op_data.get(LayoutField.SUB_ID)
        if sub_id:
            # recursively go through this
            subcommand = data_to_node(data, sub_id, op_name, data.get(sub_id, {}))
            subcommand.bugs.extend(field_to_list(op_data, LayoutField.BUG_IDS))
            children.append(subcommand)
            continue

        # use the current op-data to create a node -- it will be short
        op_id = op_data.get(LayoutField.OP_ID)
        children.append(data_to_node(data, op_id, op_name, op_data))

    return LayoutNode(
        command=command,
        identifier=identifier,
        description=description,
        bugs=bugs,
        summary_fields=summary_fields,
        extra=extra,
        children=children,
        pagination=pagination,
    )


def parse_to_tree(data: dict[str, Any], start: str = DEFAULT_START) -> LayoutNode:
    """Put the data into a tree structure starting at start."""
    top = data.get(start, {})
    if not top:
        raise ValueError(f"No start value found for '{start}'")

    return data_to_node(data, start, start, top)


def subcommand_missing_properties(data: dict[str, Any]) -> dict[str, str]:
    """Look for missing properties in the sub-commands."""
    errors = {}
    for sub_name, _sub_data in data.items():
        sub_data = deepcopy(_sub_data or {})
        missing = []

        # check top-level fields
        for k in (LayoutField.DESCRIPTION, LayoutField.OPERATIONS):
            if k not in sub_data:
                missing.append(k)

        # check each operations
        for index, op_data in enumerate(sub_data.get(LayoutField.OPERATIONS, [])):
            identifier = op_data.get(LayoutField.NAME) or f"operation[{index}]"
            if LayoutField.NAME not in op_data:
                missing.append(f"{identifier} {LayoutField.NAME.value}")
            if LayoutField.OP_ID not in op_data and LayoutField.SUB_ID not in op_data:
                missing.append(f"{identifier} {LayoutField.OP_ID.value} or {LayoutField.SUB_ID.value}")

        if missing:
            errors[sub_name] = ", ".join(missing)

    return errors


def operation_duplicates(data: dict[str, Any]) -> dict[str, Any]:
    """Look for command operations with redundant names (within each command)."""
    errors = {}

    for sub_name, _sub_data in data.items():
        # check each operations
        values = {}
        sub_data = deepcopy(_sub_data or {})
        for index, op_data in enumerate(sub_data.get(LayoutField.OPERATIONS, [])):
            name = op_data.get(LayoutField.NAME)
            if not name:
                continue

            indices = values.get(name, [])
            values[name] = indices + [index]

        multiples = []
        for name, indices in values.items():
            if len(indices) > 1:
                multiples.append(f"{name} at {', '.join([str(x) for x in indices])}")

        if multiples:
            errors[sub_name] = "; ".join(sorted(multiples))

    return errors


def operation_order(data: dict[str, Any]) -> dict[str, Any]:
    """Check the operations order for each subcommand."""
    errors = {}

    for sub_name, _sub_data in data.items():
        sub_data = deepcopy(_sub_data or {})
        op_names = [op.get(LayoutField.NAME) for op in sub_data.get(LayoutField.OPERATIONS, [])]
        if op_names != sorted(op_names):
            errors[sub_name] = ", ".join(sorted(op_names))

    return errors


def subcommand_references(data: dict[str, Any], start: str = DEFAULT_START) -> tuple[set[str], set[str]]:
    """Find missing and unused subcommand refeferences."""
    referenced = set()
    for _sub_data in data.values():
        sub_data = deepcopy(_sub_data or {})
        refs = [
            op.get(LayoutField.SUB_ID)
            for op in sub_data.get(LayoutField.OPERATIONS, [])
            if op.get(LayoutField.SUB_ID)
        ]
        referenced.update(refs)

    names = set(data.keys())
    unused = names - referenced - {start}
    missing = referenced - names

    return unused, missing


def subcommand_order(data: dict[str, Any], start: str = DEFAULT_START) -> list[str]:
    """Check the order of the sub-commands."""
    misordered = []
    names = list(data.keys())
    if not names:
        return misordered

    if names[0] != start:
        misordered.append(f"First should be {start}")
    else:
        # the remainer of the list
        names = names[1:]

    if len(names) < 2:  # noqa: PLR2004
        return misordered

    # start by populting the last
    last = names[0]
    names = names[1:]

    for sub_name in names:
        if sub_name < last:
            misordered.append(f"{sub_name} < {last}")
        last = sub_name

    return misordered


def check_pagination_definitions(data: dict[str, Any]) -> dict[str, str]:
    """Check for issues with the pagnination parameters that would potentially cause confusion."""
    errors = {}

    for sub_name, _sub_data in data.items():
        sub_data = deepcopy(_sub_data or {})
        for op in sub_data.get(LayoutField.OPERATIONS, []):
            page_params = op.get(LayoutField.PAGINATION)
            if not page_params:
                continue

            reasons = []

            extra_keys = [k for k in page_params.keys() if not PaginationField.contains(k)]
            if extra_keys:
                reasons.append(f"unsupported parameters: {', '.join(extra_keys)}")
            if page_params.get(PaginationField.NEXT_HEADER) and page_params.get(PaginationField.NEXT_PROP):
                reasons.append("cannot have next URL in both header and body property")
            if page_params.get(PaginationField.ITEM_START) and page_params.get(PaginationField.PAGE_START):
                reasons.append("start can only be specified with page or item paramter")

            if reasons:
                full_name = f"{sub_name}.{op.get(LayoutField.NAME)}"
                errors[full_name] = '; '.join(reasons)

    return errors

def file_to_tree(filename: str, start: str = DEFAULT_START) -> LayoutNode:
    """Open filename and parse to a LayoutNode tree."""
    data = open_layout(filename)
    return parse_to_tree(data, start)
