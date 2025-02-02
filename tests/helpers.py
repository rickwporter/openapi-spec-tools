from pathlib import Path
from typing import Any

from oas_tools.utils import open_oas

ASSET_PATH = Path(__file__).parent / "assets"


def asset_filename(filename: str) -> str:
    return str(ASSET_PATH / filename)


def open_test_oas(filename: str) -> Any:
    return open_oas(asset_filename(filename))
