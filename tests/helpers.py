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
