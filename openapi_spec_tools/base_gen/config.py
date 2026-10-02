"""Configuration data used to construct a base generator."""
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel

from openapi_spec_tools.types import ContentType


class GeneratorConfig(BaseModel):
    """Data elements accepted by the BaseGenerator initializer.

    Most of the data elements intentionally default to None -- this is done
    to allow for determining which items are set vs just using default values.
    """

    package_name: str
    supported_content: list[ContentType] | None = None
    max_help_length: int | None = None
    reserved: set[str] | None = None
    conflict_suffix: str | None = None
    copyright: str | None = None
    infra_files: dict[str, str] | None = None
    infra_replacements: dict[str, str] | None = None
    test_files: dict[str, str] | None = None
    test_replacements: dict[str, str] | None = None
    env_host: str | list[str] | None = None
    env_key: str | list[str] | None = None
    env_timeout: str | list[str] | None = None
    env_log_level: str | list[str] | None = None
    default_host: str | None = None
    default_log_level: str | None = None
    default_timeout: int | None = None

    @classmethod
    def from_yaml(cls, filename: str | Path) -> Self:
        """Read configuration properties from a YAML file."""
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(filename)

        with open(path, encoding="utf-8", newline="\n") as fp:
            data = yaml.safe_load(fp)

        return cls.model_validate(data or {})

    @staticmethod
    def resolve_path_keys(original: dict[str, str]) -> dict[Path, str]:
        """Resolve the key string to a Path."""
        if not original:
            return {}

        result: dict[Path, str] = {}
        base_dir = Path(__file__).parent.parent
        base_name = base_dir.name + "/"
        for key, value in original.items():
            updated_key = base_dir / key.split(base_name)[1] if base_name in key else Path(key)
            # TODO: warn if updated key does not exist?
            result[updated_key] = value

        return result
