"""Configuration data used to construct a layout generator."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from openapi_spec_tools.types import ContentType


class LayoutConfig(BaseModel):
    """Data elements accepted by the LayoutGenerator initializer.

    The data elements intentionally default to None -- this is done
    to allow for determining which items are set vs just using default values.
    """

    prefix: str | None = None
    max_help_length: int | None = None
    supported_content: list[ContentType] | None = None
    common_operations: dict[str, str] | None = None
    page_size_params: str | list[str] | None = None
    page_start_params: str | list[str] | None = None
    item_start_params: str | list[str] | None = None
    items_properties: str | list[str] | None = None
    next_properties: str | list[str] | None = None
    next_headers: str | list[str] | None = None

    @classmethod
    def from_yaml(cls, filename: str | Path) -> LayoutConfig:
        """Read configuration properties from a YAML file."""
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(filename)

        with open(path, encoding="utf-8", newline="\n") as fp:
            data = yaml.safe_load(fp)

        return cls.model_validate(data or {})
