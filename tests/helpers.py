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


def deltas(lhs: dict[str, Any], rhs: dict[str, Any]) -> list[str]:
    """Find top-level properties with differences in values.

    Due to ordering diffs, it is often difficult to see the deltas. This tells top-level keys for values that
    have differences.
    """
    lkeys = set(lhs.keys())
    rkeys = set(rhs.keys())
    result = lkeys.difference(rkeys) | rkeys.difference(lkeys)
    common = lkeys.intersection(rkeys)
    for key in common:
        if lhs.get(key) == rhs.get(key):
            continue

        result.add(key)

    return list(result)
