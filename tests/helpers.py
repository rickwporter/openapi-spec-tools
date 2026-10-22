import io
from pathlib import Path
from typing import Any

from openapi_spec_tools.utils import open_oas

ASSET_PATH = Path(__file__).parent / "assets"


class StringIo(io.StringIO):
    """Convenience class to remove the \r characters from the return value -- make testing on Windoz easier."""

    def getvalue(self) -> str:
        return super().getvalue().replace("\r", "")


def asset_filename(filename: str) -> str:
    return str(ASSET_PATH / filename)


def open_test_oas(filename: str) -> Any:
    return open_oas(asset_filename(filename))


def deltas(lhs: Any, rhs: Any) -> dict[str, Any] | str:
    """Recursively describe differences between ``lhs`` and ``rhs``.

    Dictionaries and lists are walked so nested values can be compared. A key or list item present only in
    ``lhs`` is ``missing``. A key or list item present only in ``rhs`` is ``added``. Other differing values are
    reported as ``repr(lhs) != repr(rhs)``. Equal values produce an empty dictionary. List items are compared
    by position and recorded under ``item[{index}]``.
    """
    if isinstance(lhs, dict) and isinstance(rhs, dict):
        return _dict_deltas(lhs, rhs)
    if isinstance(lhs, list) and isinstance(rhs, list):
        return _list_deltas(lhs, rhs)
    if lhs != rhs:
        return f"{lhs!r} != {rhs!r}"
    return {}


def _dict_deltas(lhs: dict[str, Any], rhs: dict[str, Any]) -> dict[str, Any]:
    """Return nested differences for two dictionaries."""
    result: dict[str, Any] = {}
    for key in sorted(set(lhs) | set(rhs)):
        if key not in rhs:
            result[key] = "missing"
        elif key not in lhs:
            result[key] = "added"
        elif lhs[key] != rhs[key]:
            result[key] = deltas(lhs[key], rhs[key])
    return result


def _list_deltas(lhs: list[Any], rhs: list[Any]) -> dict[str, Any]:
    """Return positional differences for two lists."""
    result: dict[str, Any] = {}
    shared = min(len(lhs), len(rhs))
    for index in range(shared):
        if lhs[index] != rhs[index]:
            result[f"item[{index}]"] = deltas(lhs[index], rhs[index])
    for index in range(shared, len(lhs)):
        result[f"item[{index}]"] = "missing"
    for index in range(shared, len(rhs)):
        result[f"item[{index}]"] = "added"
    return result
