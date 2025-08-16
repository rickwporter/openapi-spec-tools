import os
from typing import Optional


def env_string(varname: str, default: Optional[str], except_missing: bool = False) -> Optional[str]:
    value = os.environ.get(varname)
    if value is not None:
        return value
    if except_missing:
        raise ValueError(f"Missing {varname} value")
    return default


def env_int(varname: str, default: Optional[int], except_missing: bool = False) -> Optional[int]:
    value = os.environ.get(varname)
    if value is not None:
        return int(value)
    if except_missing:
        raise ValueError(f"Missing {varname} value")
    return default
