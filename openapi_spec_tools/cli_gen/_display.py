"""Implementation for displaying data in a user-friendly fashion."""
from enum import Enum
from gettext import gettext
from typing import Any
from typing import Optional

import yaml
from rich.box import HEAVY_HEAD
from rich.markup import escape
from rich.table import Table

from openapi_spec_tools.cli_gen._console import console_factory

DEFAULT_ROW_PROPS = {
    "justify": "left",
    "no_wrap": True,
    "overflow": "ignore",
}

# allow for i18n/l8n
ITEMS = gettext("Items")
PROPERTY = gettext("Property")
PROPERTIES = gettext("Properties")
VALUE = gettext("Value")
VALUES = gettext("Values")
UNKNOWN = gettext("Unknown")
FOUND_ITEMS = gettext("Found {} items")
ELLIPSIS = gettext("...")

OBJECT_HEADERS = [PROPERTY, VALUE]

KEY_FIELDS = ["name", "id"]
URL_PREFIXES = ["http://", "https://", "ftp://"]

KEY_MAX_LEN = 35
VALUE_MAX_LEN = 50
URL_MAX_LEN = 100


# NOTE: the key field of dictionaries are expected to be be `str`, `int`, `float`, but use
#       `Any` readability.


class TableConfig:
    """Configuration for customizing the table outputs.

    The defaults provide a standard look and feel, but can be overridden to all customization.
    """

    def __init__(
        self,
        items_label: str = ITEMS,
        property_label: str = PROPERTY,
        properties_label: str = PROPERTIES,
        value_label: str = VALUE,
        values_label: str = VALUES,
        unknown_label: str = UNKNOWN,
        items_caption: str = FOUND_ITEMS,
        url_prefixes: list[str] = URL_PREFIXES,
        url_max_len: int = URL_MAX_LEN,
        key_fields: list[str] = KEY_FIELDS,
        key_max_len: int = KEY_MAX_LEN,
        value_max_len: int = VALUE_MAX_LEN,
        row_properties: dict[str, Any] = DEFAULT_ROW_PROPS,
    ):
        self.items_label = items_label
        self.property_label = property_label
        self.properties_label = properties_label
        self.value_label = value_label
        self.values_label = values_label
        self.unknown_label = unknown_label
        self.items_caption = items_caption
        self.url_prefixes = url_prefixes
        self.url_max_len = url_max_len
        self.key_fields = key_fields
        self.key_max_len = key_max_len
        self.value_max_len = value_max_len
        self.row_properties = row_properties


class RichTable(Table):
    """Wrapper for the rich.Table to provide some methods for adding complex items."""

    def __init__(
        self,
        *args: Any,
        outer: bool = True,
        row_props: dict[str, Any] = DEFAULT_ROW_PROPS,
        **kwargs: Any,
    ):
        super().__init__(
            # items with "regular" defaults
            highlight=kwargs.pop("highlight", True),
            row_styles=kwargs.pop("row_styles", None),
            expand=kwargs.pop("expand", False),
            caption_justify=kwargs.pop("caption_justify", "left"),
            border_style=kwargs.pop("border_style", None),
            leading=kwargs.pop(
                "leading", 0
            ),  # warning: setting to non-zero disables lines
            # these items take queues from `outer`
            show_header=kwargs.pop("show_header", outer),
            show_edge=kwargs.pop("show_edge", outer),
            box=HEAVY_HEAD if outer else None,
            **kwargs,
        )
        for name in args:
            self.add_column(name, **row_props)


def _truncate(s: str, max_length: int) -> str:
    """Truncate the provided string to a maximum of max_length (including elipsis)."""
    if len(s) < max_length:
        return s
    return s[: max_length - 3] + ELLIPSIS


def _get_name_key(item: dict[Any, Any], key_fields: list[str]) -> Optional[str]:
    """Attempt to find an identifying value."""
    for k in key_fields:
        key = str(k)
        if key in item:
            return key

    return None


def _get_other_key(item: dict[Any, Any], name_key: str) -> Optional[str]:
    """Find the "other" key (if there's just one value)."""
    keys = set(item.keys())
    keys.remove(name_key)
    if len(keys) != 1:
        return None

    return keys.pop()


def _is_url(s: str, url_prefixes: list[str]) -> bool:
    """Rudimentary check for somethingt starting with URL prefix."""
    return any(s.startswith(p) for p in url_prefixes)


def _safe(v: Any) -> str:
    """Convert 'v' to a string that is properly escaped."""
    return escape(str(v))


def _create_list_table(
    items: list[dict[Any, Any]], outer: bool, config: TableConfig
) -> RichTable:
    """Create a table from a list of dictionary items.

    If an identifying "name key" is found (in the first entry), the table will have 2 columns: name, Properties
    If no identifying "name key" is found, the table will be a single column table with the properties.

    NOTE: nesting is done as needed
    """
    caption = config.items_caption.format(len(items)) if outer else None
    name_key = _get_name_key(items[0], config.key_fields)
    if not name_key:
        # without identifiers just create table with one "Values" column
        table = RichTable(
            config.values_label,
            outer=outer,
            show_lines=True,
            caption=caption,
            row_props=config.row_properties,
        )
        for item in items:
            table.add_row(_table_cell_value(item, config))
        return table

    # if there's just one property besides the key, use that as the label
    name_label = name_key[0].upper() + name_key[1:]
    other_key = _get_other_key(items[0], name_key)
    if other_key:
        other_name = other_key[0].upper() + other_key[1:]
        fields = [name_label, other_name]
        table = RichTable(
            *fields,
            outer=outer,
            show_lines=True,
            caption=caption,
            row_props=config.row_properties,
        )
        for item in items:
            # id may be an int, so convert to string before truncating
            name = _safe(item.pop(name_key, config.unknown_label))
            body = _table_cell_value(item.get(other_key), config)
            table.add_row(_truncate(name, config.key_max_len), body)
        return table

    # create a table with identifier in left column, and rest of data in right column
    fields = [name_label, config.properties_label]
    table = RichTable(
        *fields,
        outer=outer,
        show_lines=True,
        caption=caption,
        row_props=config.row_properties,
    )
    for item in items:
        # id may be an int, so convert to string before truncating
        name = _safe(item.pop(name_key, config.unknown_label))
        body = _table_cell_value(item, config)
        table.add_row(_truncate(name, config.key_max_len), body)

    return table


def _create_object_table(
    obj: dict[Any, Any], outer: bool, config: TableConfig
) -> RichTable:
    """Create a table of a dictionary object.

    NOTE: nesting is done in the right column as needed.
    """
    headers = [config.property_label, config.value_label]
    table = RichTable(
        *headers, outer=outer, show_lines=False, row_props=config.row_properties
    )
    for k, v in obj.items():
        name = _safe(k)
        table.add_row(_truncate(name, config.key_max_len), _table_cell_value(v, config))

    return table


def _table_cell_value(obj: Any, config: TableConfig) -> Any:
    """Create the "inner" value for a table cell.

    Depending on the input value type, the cell may look different. If a dict, or list[dict],
    an inner table is created. Otherwise, the object is converted to a printable value.
    """
    value: Any = None
    if isinstance(obj, dict):
        value = _create_object_table(obj, outer=False, config=config)
    elif isinstance(obj, list) and obj:
        if isinstance(obj[0], dict):
            value = _create_list_table(obj, outer=False, config=config)
        else:
            values = [str(x) for x in obj]
            s = _safe(", ".join(values))
            value = _truncate(s, config.value_max_len)
    else:
        s = _safe(obj)
        max_len = (
            config.url_max_len
            if _is_url(s, config.url_prefixes)
            else config.value_max_len
        )
        value = _truncate(s, max_len)

    return value


def rich_table_factory(obj: Any, config: Optional[TableConfig] = None) -> RichTable:
    """Create a RichTable (alias for rich.table.Table) from the object."""
    config = config or TableConfig()
    if isinstance(obj, dict):
        return _create_object_table(obj, outer=True, config=config)

    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return _create_list_table(obj, outer=True, config=config)

    # this is a list of "simple" properties
    if (
        isinstance(obj, list)
        and obj
        and all(
            item is None or isinstance(item, (str, float, bool, int)) for item in obj
        )
    ):
        caption = config.items_caption.format(len(obj))
        table = RichTable(
            config.items_label,
            outer=True,
            show_lines=True,
            caption=caption,
            row_props=config.row_properties,
        )
        for item in obj:
            table.add_row(_table_cell_value(item, config))
        return table

    raise ValueError(f"Unable to create table for type {type(obj).__name__}")


###################################################################################################
# Below will remain even after the code from https://github.com/fastapi/typer/pull/1099 merges.
###################################################################################################
class OutputFormat(str, Enum):
    """Output text format for received data."""

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class OutputStyle(str, Enum):
    """Text style options for none, bold-only, or bold-and-color."""

    NONE = "none"
    BOLD = "bold"
    ALL = "all"


def summary(obj: Any, properties: list[str]) -> Any:
    """Get the item with just the specified properties."""
    if obj is None:
        return None

    if isinstance(obj, list):
        # recursively call for each object in list
        return [summary(item, properties) for item in obj]

    return {prop: obj.get(prop) for prop in properties}


def display(obj: Any, fmt: OutputFormat, style: OutputStyle, indent: int = 2) -> None:
    """Display the data provided in obj, according to the formating arguments."""
    no_color = style != OutputStyle.ALL
    highlight = style != OutputStyle.NONE
    console = console_factory(no_color=no_color, highlight=highlight)

    if isinstance(obj, str):
        console.print(_safe(obj))
        return

    if fmt == OutputFormat.JSON:
        console.print_json(data=obj, indent=indent, highlight=highlight)
        return

    if fmt == OutputFormat.YAML:
        console.print(_safe(yaml.dump(obj, indent=indent)))
        return

    if not obj:
        console.print("Nothing found")
        return

    table = rich_table_factory(obj)
    console.print(table)
    return
