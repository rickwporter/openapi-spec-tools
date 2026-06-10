import os


def env_string(varname: str, default: str | None = None, except_missing: bool = False) -> str | None:
    value = os.environ.get(varname)
    if value is not None:
        return value
    if except_missing:
        raise ValueError(f"Missing {varname} value")
    return default


def env_int(varname: str, default: int | None = None, except_missing: bool = False) -> int | None:
    value = os.environ.get(varname)
    if value is not None:
        return int(value)
    if except_missing:
        raise ValueError(f"Missing {varname} value")
    return default
