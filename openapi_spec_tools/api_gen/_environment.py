import os


def env_string(varnames: str | list[str], default: str | None = None, except_missing: bool = False) -> str | None:
    """Get string value from environment.

    When no value is found, return the default or throw a ValueError (if except_missing is True).
    """
    varnames = [varnames] if isinstance(varnames, str) else varnames

    for varname in varnames:
        value = os.environ.get(varname)
        if value is not None:
            return value

    if except_missing:
        raise ValueError(f"Missing {', '.join(varnames)} value(s)")
    return default


def env_int(varnames: str | list[str], default: int | None = None, except_missing: bool = False) -> int | None:
    """Get integer value from environment.

    When no value is found, return the default or throw a ValueError (if except_missing is True).
    """
    varnames = [varnames] if isinstance(varnames, str) else varnames

    for varname in varnames:
        value = os.environ.get(varname)
        if value is not None:
            return int(value)

    if except_missing:
        raise ValueError(f"Missing {', '.join(varnames)} value(s)")
    return default
