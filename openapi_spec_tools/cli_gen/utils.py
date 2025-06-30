"""Implement some basic utilities used in code generation."""
import re
from typing import Any

SIMPLE_TRANSLATIONS = str.maketrans(
    {
        "\\": r"\\",
        "'": r"\'",
        '"': r"\"",
    },
)


def to_snake_case(text: str) -> str:
    """Convert provided text to a_snake_case value."""
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def to_camel_case(text: str) -> str:
    """Convert provided text to aCamelCase value."""
    return re.sub(r'_([a-z])', lambda match: match.group(1).upper(), text)


def maybe_quoted(item: Any) -> str:
    """Add leading/trailing quotes to an item of type string, otherwise just convert item to a string."""
    if isinstance(item, str):
        return quoted(item)

    return str(item)


def quoted(s: str) -> str:
    """Double quote the provided string (and escape properly)."""
    return f'"{s.translate(SIMPLE_TRANSLATIONS)}"'


def simple_escape(text: str) -> str:
    """Replace characters that are problematic in simple quoted strings."""
    lines = [_.strip() for _ in text.splitlines() if _.strip()]
    if not lines:
        return ""
    return lines[0].translate(SIMPLE_TRANSLATIONS)


def set_missing(obj: dict[str, Any], key: str, value: Any) -> None:
    """Set key/value into obj if the key is NOT already in the object."""
    if key not in obj:
        obj[key] = value
