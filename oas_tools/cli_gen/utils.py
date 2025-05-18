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
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def to_camel_case(text: str) -> str:
    return re.sub(r'_([a-z])', lambda match: match.group(1).upper(), text)


def maybe_quoted(item: Any) -> str:
    if isinstance(item, str):
        return f'"{item}"'

    return str(item)


def quoted(s: str) -> str:
    """Returns a double quoted version of the provided string"""
    return f'"{s}"'


def simple_escape(text: str) -> str:
    """Replaces characters that are problematic in simple quoted strings"""
    lines = [_.strip() for _ in text.splitlines() if _.strip()]
    if not lines:
        return ""
    return lines[0].translate(SIMPLE_TRANSLATIONS)


def set_missing(obj: dict[str, Any], key: str, value: Any) -> None:
    if key not in obj:
        obj[key] = value
